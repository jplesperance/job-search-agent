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

    def send(self, message: str) -> str | None: ...


@dataclass(frozen=True)
class NotificationResult:
    job_id: UUID
    status: NotificationStatus
    attempted: bool
    provider_message_id: str | None = None
    error: str | None = None


class ConsoleNotifier:
    channel = "console"

    def send(self, message: str) -> str:
        print(message)
        return f"console:{uuid4()}"


class TwilioSmsNotifier:
    channel = "sms"

    def __init__(
        self,
        *,
        account_sid: str,
        auth_token: str,
        from_number: str,
        to_number: str,
    ) -> None:
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.to_number = to_number

    def send(self, message: str) -> str | None:
        response = httpx.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json",
            auth=(self.account_sid, self.auth_token),
            data={"From": self.from_number, "To": self.to_number, "Body": message},
            timeout=20.0,
        )
        response.raise_for_status()
        return response.json().get("sid")


def build_notifier(settings: Settings) -> Notifier | None:
    provider = settings.notification_provider.strip().casefold()
    if provider in {"", "disabled", "none", "off"}:
        return None
    if provider == "console":
        return ConsoleNotifier()
    if provider == "twilio":
        required = {
            "TWILIO_ACCOUNT_SID": settings.twilio_account_sid,
            "TWILIO_AUTH_TOKEN": settings.twilio_auth_token,
            "TWILIO_FROM_NUMBER": settings.twilio_from_number,
            "NOTIFICATION_RECIPIENT": settings.notification_recipient,
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise RuntimeError(
                "Twilio is configured but required settings are missing: "
                + ", ".join(missing)
            )
        return TwilioSmsNotifier(
            account_sid=settings.twilio_account_sid or "",
            auth_token=settings.twilio_auth_token or "",
            from_number=settings.twilio_from_number or "",
            to_number=settings.notification_recipient or "",
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
        if candidate.source_url:
            lines.append(candidate.source_url)
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
        row.payload_hash = hashlib.sha256(message.encode("utf-8")).hexdigest()
        row.status = NotificationStatus.PENDING.value
        row.attempt_count += 1
        row.last_attempt_at = datetime.now(timezone.utc)
        row.last_error = None
        self.session.flush()

        try:
            provider_id = self.notifier.send(message)
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
            payload_hash=hashlib.sha256(message.encode("utf-8")).hexdigest(),
        )
        self.session.add(row)
        self.session.flush()
        return NotificationResult(
            candidate.job_id,
            NotificationStatus.SUPPRESSED,
            attempted=False,
        )
