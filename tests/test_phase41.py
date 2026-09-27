from __future__ import annotations

from job_agent.config.settings import Settings
from job_agent.db.tables import JobSourcePostingRow, NotificationStateRow
from job_agent.services.canonical_jobs import (
    description_similarity,
    normalize_company,
    normalize_source_url,
    normalize_title,
)
from job_agent.services.notifications import ConsoleNotifier, build_notifier


def test_canonical_identity_normalization_is_conservative_and_stable():
    assert normalize_company("Acme, Inc.") == "acme"
    assert normalize_title("Sr. Manager, Application Security") == "senior manager application security"
    assert (
        normalize_source_url("https://jobs.example.com/123/?utm_source=linkedin&ref=x")
        == "https://jobs.example.com/123"
    )
    assert description_similarity("Threat modeling and AppSec", "Threat modeling and AppSec") == 1.0


def test_phase41_tables_enforce_idempotency_keys():
    source_unique = {
        tuple(column.name for column in constraint.columns)
        for constraint in JobSourcePostingRow.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    notification_unique = {
        tuple(column.name for column in constraint.columns)
        for constraint in NotificationStateRow.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("source", "external_id") in source_unique
    assert ("job_id", "channel", "notification_type") in notification_unique


def test_notifier_configuration_defaults_disabled_and_supports_console():
    assert build_notifier(Settings(notification_provider="disabled")) is None
    notifier = build_notifier(Settings(notification_provider="console"))
    assert isinstance(notifier, ConsoleNotifier)
    assert notifier.channel == "console"
