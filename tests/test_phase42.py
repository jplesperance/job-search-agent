from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from job_agent.config.settings import Settings
from job_agent.db.tables import DiscoverySourceHealthRow
from job_agent.domain.discovery import (
    DiscoveryProvider, DiscoveryRunStatus, DiscoverySourceSummary,
)
from job_agent.services.discovery_adapters import (
    AdapterRegistry, DiscoveryFetchError, SmartRecruitersAdapter,
)
from job_agent.services.discovery_health import DiscoveryHealthService, transition_state


def source():
    return DiscoverySourceSummary(
        id=uuid4(), company="Acme", provider=DiscoveryProvider.SMARTRECRUITERS,
        board_identifier="acme", enabled=True, priority=100, config={},
        created_at=datetime.now(timezone.utc),
    )


class Http:
    def __init__(self, pages, details=None):
        self.pages = pages
        self.details = details or {}
        self.calls = []

    def get_json(self, url):
        self.calls.append(url)
        if "?" in url:
            return self.pages[url.split("offset=")[-1]]
        return self.details[url.rsplit("/", 1)[-1]]


def test_smartrecruiters_details_loaded_after_prefilter():
    http = Http(
        {"0": {"totalFound": 1, "content": [
            {"id": "123", "name": "Director of Application Security",
             "releasedDate": "2026-09-15T00:00:00Z",
             "location": {"city": "San Jose", "region": "CA", "remote": False}}
        ]}},
        {"123": {"applyUrl": "https://jobs.smartrecruiters.com/acme/123",
                 "location": {"city": "San Jose", "region": "CA", "remote": True},
                 "jobAd": {"sections": {
                     "jobDescription": {"text": "Own secure architecture and the enterprise application security program."},
                     "qualifications": {"text": "Experience with threat modeling, cloud security, and AppSec leadership."},
                 }}}},
    )
    adapter = SmartRecruitersAdapter(http)
    jobs = adapter.fetch(source())
    assert len(jobs) == 1
    assert "pending" not in jobs[0].description_raw.casefold()
    enriched = adapter.enrich(source(), jobs[0])
    assert "threat modeling" in enriched.description_raw
    assert enriched.work_arrangement == "remote"
    assert str(enriched.source_url).startswith("https://jobs.smartrecruiters.com/")
    assert len(http.calls) == 2


def test_smartrecruiters_paging_must_be_complete():
    http = Http({
        "0": {"totalFound": 101, "content": [
            {"id": "1", "name": "Security Director", "location": {}}]},
        "100": {"totalFound": 101, "content": []},
    })
    with pytest.raises(DiscoveryFetchError, match="pagination ended"):
        SmartRecruitersAdapter(http).fetch(source())


def test_smartrecruiters_rejects_missing_total():
    with pytest.raises(DiscoveryFetchError, match="totalFound"):
        SmartRecruitersAdapter(Http({"0": {"content": []}})).fetch(source())


def test_smartrecruiters_rejects_missing_full_description():
    http = Http({"0": {"totalFound": 1, "content": [
        {"id": "99", "name": "Director of Security"}]}},
        {"99": {"jobAd": {"sections": {"jobDescription": {"text": "<p>Short</p>"}}}}},
    )
    adapter = SmartRecruitersAdapter(http)
    with pytest.raises(DiscoveryFetchError, match="incomplete"):
        adapter.enrich(source(), adapter.fetch(source())[0])


def test_registry_includes_smartrecruiters():
    assert isinstance(AdapterRegistry(Http({})).get(DiscoveryProvider.SMARTRECRUITERS), SmartRecruitersAdapter)


def _health_row():
    return DiscoverySourceHealthRow(
        source_id=uuid4(), consecutive_failures=0, last_status="unknown",
        incident_open=False, failure_alert_sent=False,
        recovery_alert_pending=False, updated_at=datetime.now(timezone.utc),
    )


def test_health_escalates_after_repeated_failure_and_resolves():
    row = _health_row()
    now = datetime.now(timezone.utc)
    transition_state(row, DiscoveryRunStatus.FAILED, now, "HTTP 503")
    assert row.consecutive_failures == 1
    assert row.incident_open
    transition_state(row, DiscoveryRunStatus.PARTIAL, now, "missing detail")
    assert row.consecutive_failures == 2
    assert row.last_error == "missing detail"
    row.failure_alert_sent = True
    transition_state(row, DiscoveryRunStatus.COMPLETED, now)
    assert row.recovery_alert_pending
    assert not row.incident_open
    assert row.consecutive_failures == 0
    assert row.last_error is None


def test_health_does_not_emit_recovery_when_not_alerted():
    row = _health_row()
    now = datetime.now(timezone.utc)
    transition_state(row, DiscoveryRunStatus.FAILED, now, "HTTP 429")
    transition_state(row, DiscoveryRunStatus.COMPLETED, now)
    assert not row.recovery_alert_pending


def test_new_outage_invalidates_old_pending_recovery():
    row = _health_row()
    now = datetime.now(timezone.utc)
    transition_state(row, DiscoveryRunStatus.FAILED, now, "API")
    row.failure_alert_sent = True
    transition_state(row, DiscoveryRunStatus.COMPLETED, now)
    assert row.recovery_alert_pending
    transition_state(row, DiscoveryRunStatus.FAILED, now, "API")
    assert not row.recovery_alert_pending


def test_health_alerts_disabled_by_default():
    assert Settings(_env_file=None).discovery_health_alerts_enabled is False

class HealthSession:
    def __init__(self, row, source_row):
        self.row = row
        self.source = source_row
        self.commits = 0

    def execute(self, query):
        return SimpleNamespace(scalars=lambda: [self.row])

    def get(self, cls, identifier):
        if cls.__name__ == "DiscoverySourceRow":
            return self.source
        return self.row

    def commit(self):
        self.commits += 1


class RecordingNotifier:
    channel = "console"

    def __init__(self, fail=False):
        self.messages = []
        self.fail = fail

    def send(self, message, *, title=None, url=None):
        self.messages.append((title, message))
        if self.fail:
            raise RuntimeError("temporary transport failure")
        return "ok"


def test_health_alert_once_then_recovery_once():
    row = _health_row()
    src = SimpleNamespace(enabled=True, company="Acme", provider="smartrecruiters")
    session = HealthSession(row, src)
    notifier = RecordingNotifier()
    monitor = DiscoveryHealthService(session, notifier=notifier, alerts_enabled=True, failure_threshold=2)
    now = datetime.now(timezone.utc)
    transition_state(row, DiscoveryRunStatus.FAILED, now, "unavailable")
    assert monitor.send_alerts() == (0, 0)
    transition_state(row, DiscoveryRunStatus.FAILED, now, "unavailable")
    assert monitor.send_alerts() == (1, 0)
    assert monitor.send_alerts() == (0, 0)
    transition_state(row, DiscoveryRunStatus.COMPLETED, now)
    assert monitor.send_alerts() == (1, 0)
    assert monitor.send_alerts() == (0, 0)
    assert len(notifier.messages) == 2


def test_health_alert_failure_remains_retryable():
    row = _health_row()
    source_row = SimpleNamespace(enabled=True, company="Acme", provider="greenhouse")
    session = HealthSession(row, source_row)
    notifier = RecordingNotifier(fail=True)
    monitor = DiscoveryHealthService(session, notifier=notifier, alerts_enabled=True, failure_threshold=2)
    now = datetime.now(timezone.utc)
    transition_state(row, DiscoveryRunStatus.FAILED, now, "timeout")
    transition_state(row, DiscoveryRunStatus.FAILED, now, "timeout")
    assert monitor.send_alerts() == (0, 1)
    assert not row.failure_alert_sent
    notifier.fail = False
    assert monitor.send_alerts() == (1, 0)
    assert row.failure_alert_sent


def test_health_no_delivery_when_opted_out():
    row = _health_row()
    session = HealthSession(row, SimpleNamespace(enabled=True, company="Acme", provider="greenhouse"))
    notifier = RecordingNotifier()
    monitor = DiscoveryHealthService(session, notifier=notifier, alerts_enabled=False)
    transition_state(row, DiscoveryRunStatus.FAILED, datetime.now(timezone.utc), "error")
    transition_state(row, DiscoveryRunStatus.FAILED, datetime.now(timezone.utc), "error")
    assert monitor.send_alerts() == (0, 0)
    assert not notifier.messages


def test_empty_established_board_is_failed_without_closing_jobs():
    from job_agent.services.discovery import DiscoveryService
    from job_agent.domain.discovery import DiscoveryRunRequest, DiscoveryRunSummary
    from job_agent.domain.models import TargetingPolicy

    prior_source = source().model_copy(update={"last_checked_at": datetime.now(timezone.utc)})

    class Repo:
        closed = False
        def get_source(self, source_id): return prior_source
        def start_run(self, source_id, started_at): return uuid4()
        def mark_unseen_closed(self, **kwargs):
            self.closed = True
            raise AssertionError("Existing jobs must not be closed")
        def finish_run(self, *, run_id, completed_at, status, counters, error_message):
            return DiscoveryRunSummary(
                id=run_id, source_id=prior_source.id, company=prior_source.company,
                provider=prior_source.provider, status=status,
                started_at=datetime.now(timezone.utc), completed_at=completed_at,
                error_message=error_message, **counters,
            )
        def touch_source(self, source_id, checked_at): pass

    class Policies:
        def get_active(self): return TargetingPolicy(name="s", target_titles=["Director of Security"])

    class Adapter:
        def fetch(self, src): return []

    class Registry:
        def get(self, provider): return Adapter()

    repo = Repo()
    result = DiscoveryService(
        discovery_repo=repo, policy_repo=Policies(),
        ingestion_service=SimpleNamespace(ingest=lambda x: None),
        match_service=SimpleNamespace(analyze=lambda a, b: None), adapters=Registry(),
    ).run(DiscoveryRunRequest(source_id=prior_source.id))
    assert result.runs[0].status == DiscoveryRunStatus.FAILED
    assert "Unexpected empty board" in (result.runs[0].error_message or "")
    assert repo.closed is False
