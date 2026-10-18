from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from job_agent.db.tables import DiscoverySourceHealthRow, DiscoverySourceRow
from job_agent.domain.discovery import DiscoveryRunStatus, DiscoveryRunSummary
from job_agent.services.notifications import Notifier


def transition_state(row: DiscoverySourceHealthRow, status: DiscoveryRunStatus,
                     checked_at: datetime, error: str | None = None) -> None:
    """Apply a single completed poll. Pure ORM-state transition, independently testable."""
    row.last_status = status.value
    row.last_attempt_at = checked_at
    row.updated_at = checked_at
    if status is DiscoveryRunStatus.COMPLETED:
        if row.incident_open and row.failure_alert_sent:
            row.recovery_alert_pending = True
        row.consecutive_failures = 0
        row.last_success_at = checked_at
        row.last_error = None
        row.incident_open = False
        row.incident_started_at = None
        row.failure_alert_sent = False
    else:
        # A failed or partial run is not a successful scan; do not reset failure streak.
        if not row.incident_open:
            row.recovery_alert_pending = False
            row.incident_started_at = checked_at
            row.incident_open = True
            row.failure_alert_sent = False
        row.consecutive_failures += 1
        row.last_error = (error or status.value)[:4000]


class DiscoveryHealthService:
    def __init__(self, session: Session, *, notifier: Notifier | None = None,
                 alerts_enabled: bool = False, failure_threshold: int = 2) -> None:
        self.session = session
        self.notifier = notifier
        self.alerts_enabled = alerts_enabled
        self.failure_threshold = max(1, failure_threshold)

    def record_runs(self, runs: list[DiscoveryRunSummary]) -> None:
        for run in runs:
            if run.status is DiscoveryRunStatus.RUNNING:
                continue
            row = self.session.get(DiscoverySourceHealthRow, run.source_id)
            if row is None:
                row = DiscoverySourceHealthRow(
                    source_id=run.source_id,
                    consecutive_failures=0,
                    last_status="unknown",
                    incident_open=False,
                    failure_alert_sent=False,
                    recovery_alert_pending=False,
                    updated_at=run.completed_at or datetime.now(timezone.utc),
                )
                self.session.add(row)
            transition_state(
                row,
                run.status,
                run.completed_at or datetime.now(timezone.utc),
                run.error_message,
            )
        self.session.flush()

    def send_alerts(self) -> tuple[int, int]:
        """Return (alerts_sent, alerts_failed); job notifications are independent."""
        if not self.alerts_enabled or self.notifier is None:
            return 0, 0
        sent = failed = 0
        rows = list(self.session.execute(select(DiscoverySourceHealthRow)).scalars())
        for row in rows:
            source = self.session.get(DiscoverySourceRow, row.source_id)
            if source is None or not source.enabled:
                continue
            message = None
            kind = ""
            # One failure warning per incident after a configurable threshold.
            if row.incident_open and not row.failure_alert_sent and row.consecutive_failures >= self.failure_threshold:
                kind = "failure"
                message = (
                    f"Discovery failure: {source.company} ({source.provider})\n"
                    f"{row.consecutive_failures} consecutive incomplete polls.\n"
                    f"Reason: {(row.last_error or 'unknown')[:600]}"
                )
            elif row.recovery_alert_pending and not row.incident_open:
                kind = "recovered"
                message = f"Discovery recovered: {source.company} ({source.provider})."
            if message is None:
                continue
            try:
                self.notifier.send(message, title=f"Job Agent: {kind}")
                row.last_alert_error = None
                row.last_alert_at = datetime.now(timezone.utc)
                if kind == "failure":
                    row.failure_alert_sent = True
                else:
                    row.recovery_alert_pending = False
                sent += 1
            except Exception as exc:
                row.last_alert_error = str(exc)[:1000]
                failed += 1
            # An alert state is committed before moving to the next source, minimizing
            # repeated sends if another source or job notifier fails.
            self.session.commit()
        return sent, failed


def source_health_report(session: Session, *, stale_hours: int = 12,
                         now: datetime | None = None) -> list[dict]:
    current = now or datetime.now(timezone.utc)
    threshold = current - timedelta(hours=max(1, stale_hours))
    data: list[dict] = []
    for source in session.execute(
        select(DiscoverySourceRow).where(DiscoverySourceRow.enabled.is_(True)).order_by(DiscoverySourceRow.company)
    ).scalars():
        row = session.get(DiscoverySourceHealthRow, source.id)
        last = row.last_attempt_at if row else source.last_checked_at
        # A source with no stored health record is not automatically considered failed.
        stale = source.enabled and (last is None or last < threshold)
        data.append({
            "source_id": str(source.id),
            "company": source.company,
            "provider": source.provider,
            "enabled": source.enabled,
            "last_status": row.last_status if row else "unknown",
            "last_attempt_at": last.isoformat() if last else None,
            "last_success_at": row.last_success_at.isoformat() if row and row.last_success_at else None,
            "consecutive_failures": row.consecutive_failures if row else 0,
            "incident_open": bool(row.incident_open) if row else False,
            "failure_alert_sent": bool(row.failure_alert_sent) if row else False,
            "stale": stale,
            "last_error": row.last_error if row else None,
        })
    return data
