from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from job_agent.config.settings import Settings
from job_agent.db.tables import NotificationStateRow
from job_agent.domain.discovery import DiscoveryCandidateSummary


class NotificationStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SUPPRESSED = "suppressed"


class Notifier(Protocol):
    channel: str

    def send(
        self, message: str, *, title: str | None = None, url: str | None = None
    ) -> str | None: ...


@dataclass(frozen=True)
class NotificationResult:
    job_id: UUID
    status: NotificationStatus
    attempted: bool
    provider_message_id: str | None = None
    error: str | None = None


class ConsoleNotifier:
    channel = "console"

    def send(
        self, message: str, *, title: str | None = None, url: str | None = None
    ) -> str:
        if title:
            print(title)
        print(message)
        if url:
            print(url)
        return f"console:{uuid4()}"


class PushoverNotifier:
    """Pushover HTTPS delivery; accepted message request IDs are persisted in notification_states."""

    channel = "pushover"

    def __init__(
        self,
        *,
        api_token: str,
        user_key: str,
        device: str | None = None,
    ) -> None:
        self.api_token = api_token
        self.user_key = user_key
        self.device = device

    def send(
        self,
        message: str,
        *,
        title: str | None = None,
        url: str | None = None,
    ) -> str | None:
        # Pushover limits: 1024 UTF-8 characters, 250 title characters,
        # and 512 supplementary URL characters. Keep URLs separate from text.
        if len(message) > 1024:
            raise ValueError("Pushover message exceeds 1024 characters")

        data: dict[str, str] = {
            "token": self.api_token,
            "user": self.user_key,
            "message": message,
        }
        if title:
            data["title"] = title[:250]
        if url and len(url) <= 512 and url.startswith(("https://", "http://")):
            data["url"] = url
            data["url_title"] = "Open job posting"
        if self.device:
            data["device"] = self.device

        response = httpx.post(
            "https://api.pushover.net/1/messages.json",
            data=data,
            timeout=20.0,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != 1:
            error_details = payload.get("errors") or ["unknown Pushover error"]
            if isinstance(error_details, list):
                detail = "; ".join(str(error) for error in error_details[:3])
            else:
                detail = str(error_details)
            raise RuntimeError(f"Pushover rejected notification: {detail[:500]}")
        request_id = payload.get("request")
        return str(request_id) if request_id else None


def build_notifier(settings: Settings) -> Notifier | None:
    provider = settings.notification_provider.strip().casefold()
    if provider in {"", "disabled", "none", "off"}:
        return None
    if provider == "console":
        return ConsoleNotifier()
    if provider == "pushover":
        required = {
            "PUSHOVER_API_TOKEN": settings.pushover_api_token,
            "PUSHOVER_USER_KEY": settings.pushover_user_key,
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise RuntimeError(
                "Pushover is configured but required settings are missing: "
                + ", ".join(missing)
            )
        return PushoverNotifier(
            api_token=settings.pushover_api_token or "",
            user_key=settings.pushover_user_key or "",
            device=settings.pushover_device,
        )
    raise RuntimeError(f"Unsupported notification provider: {settings.notification_provider}")


class NotificationService:
    def __init__(
        self,
        session: Session,
        notifier: Notifier,
        *,
        max_attempts: int = 3,
        notification_type: str = "new_match",
    ) -> None:
        self.session = session
        self.notifier = notifier
        self.max_attempts = max(1, max_attempts)
        self.notification_type = notification_type

    def _existing(self, job_id: UUID) -> NotificationStateRow | None:
        return self.session.execute(
            select(NotificationStateRow).where(
                NotificationStateRow.job_id == job_id,
                NotificationStateRow.channel == self.notifier.channel,
                NotificationStateRow.notification_type == self.notification_type,
            )
        ).scalar_one_or_none()

    @staticmethod
    def _message(candidate: DiscoveryCandidateSummary) -> str:
        lines = [
            f"New job match: {candidate.company} — {candidate.title}",
            f"Score: {candidate.total_score:.1f}",
            f"{candidate.location or 'Location unavailable'} | "
            f"{candidate.compensation_text or 'Salary unavailable'}",
        ]
        return "\n".join(lines)

    def notify(self, candidate: DiscoveryCandidateSummary) -> NotificationResult:
        row = self._existing(candidate.job_id)
        if row is not None:
            status = NotificationStatus(row.status)
            if status in {NotificationStatus.SENT, NotificationStatus.SUPPRESSED}:
                return NotificationResult(candidate.job_id, status, attempted=False)
            if row.attempt_count >= self.max_attempts:
                return NotificationResult(
                    candidate.job_id,
                    NotificationStatus.FAILED,
                    attempted=False,
                    error=row.last_error,
                )
        else:
            row = NotificationStateRow(
                id=uuid4(),
                job_id=candidate.job_id,
                discovery_run_id=None,
                channel=self.notifier.channel,
                notification_type=self.notification_type,
                status=NotificationStatus.PENDING.value,
                attempt_count=0,
                created_at=datetime.now(timezone.utc),
            )
            self.session.add(row)
            self.session.flush()

        message = self._message(candidate)
        fingerprint = message + "\0" + (candidate.source_url or "")
        row.payload_hash = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
        row.status = NotificationStatus.PENDING.value
        row.attempt_count += 1
        row.last_attempt_at = datetime.now(timezone.utc)
        row.last_error = None
        self.session.flush()

        try:
            provider_id = self.notifier.send(
                message,
                title="New Job Match",
                url=candidate.source_url,
            )
        except Exception as exc:
            row.status = NotificationStatus.FAILED.value
            row.last_error = str(exc)[:4000]
            self.session.flush()
            return NotificationResult(
                candidate.job_id,
                NotificationStatus.FAILED,
                attempted=True,
                error=row.last_error,
            )

        row.status = NotificationStatus.SENT.value
        row.sent_at = datetime.now(timezone.utc)
        row.provider_message_id = provider_id
        self.session.flush()
        return NotificationResult(
            candidate.job_id,
            NotificationStatus.SENT,
            attempted=True,
            provider_message_id=provider_id,
        )

    def suppress(self, candidate: DiscoveryCandidateSummary) -> NotificationResult:
        row = self._existing(candidate.job_id)
        if row is not None:
            return NotificationResult(
                candidate.job_id,
                NotificationStatus(row.status),
                attempted=False,
            )
        message = self._message(candidate)
        row = NotificationStateRow(
            id=uuid4(),
            job_id=candidate.job_id,
            discovery_run_id=None,
            channel=self.notifier.channel,
            notification_type=self.notification_type,
            status=NotificationStatus.SUPPRESSED.value,
            attempt_count=0,
            created_at=datetime.now(timezone.utc),
            payload_hash=hashlib.sha256(
                (message + "\0" + (candidate.source_url or "")).encode("utf-8")
            ).hexdigest(),
        )
        self.session.add(row)
        self.session.flush()
        return NotificationResult(
            candidate.job_id,
            NotificationStatus.SUPPRESSED,
            attempted=False,
        )
