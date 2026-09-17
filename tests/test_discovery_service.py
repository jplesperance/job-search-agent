from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from job_agent.domain.discovery import (
    DiscoveryPosting,
    DiscoveryProvider,
    DiscoveryRunRequest,
    DiscoveryRunStatus,
    DiscoveryRunSummary,
    DiscoverySourceSummary,
)
from job_agent.domain.jobs import JobIngestResponse, JobMatchResponse, LocationCompensationDecision, MatchConfidence, ParsedJobDescription
from job_agent.domain.models import TargetingPolicy
from job_agent.services.discovery import DiscoveryService, SecurityTitlePrefilter


class FakeDiscoveryRepo:
    def __init__(self, source):
        self.source = source
        self.run_id = uuid4()
        self.links = []
        self.closed = 2

    def get_source(self, source_id): return self.source if source_id == self.source.id else None
    def list_sources(self, enabled_only=False): return [self.source]
    def start_run(self, source_id, started_at): return self.run_id
    def link_job(self, **kwargs): self.links.append(kwargs)
    def mark_unseen_closed(self, **kwargs): return self.closed
    def touch_source(self, source_id, checked_at): pass
    def finish_run(self, *, run_id, completed_at, status, counters, error_message):
        return DiscoveryRunSummary(
            id=run_id, source_id=self.source.id, company=self.source.company,
            provider=self.source.provider, status=status, started_at=datetime.now(timezone.utc),
            completed_at=completed_at, error_message=error_message, **counters,
        )


class FakePolicyRepo:
    def get_active(self):
        return TargetingPolicy(
            name="primary", active=True,
            target_titles=["Director of Application Security", "Principal Security Engineer"],
        )


class FakeAdapter:
    def fetch(self, source):
        return [
            DiscoveryPosting(
                provider=source.provider, external_id="1", company=source.company,
                title="Director of Application Security", location="Palo Alto, CA",
                description_raw="Requirements: Threat modeling and application security. " * 2,
                source_url="https://example.com/1",
            ),
            DiscoveryPosting(
                provider=source.provider, external_id="2", company=source.company,
                title="Senior Accountant", location="Palo Alto, CA",
                description_raw="Own accounting systems and close process. " * 2,
                source_url="https://example.com/2",
            ),
        ]


class FakeRegistry:
    def get(self, provider): return FakeAdapter()


class FakeIngestion:
    def ingest(self, request):
        return JobIngestResponse(
            job_id=uuid4(), created=True, content_hash="x" * 64,
            parsed=ParsedJobDescription(role_family="application_security", requirements=[]),
        )


class FakeMatcher:
    def analyze(self, job_id, request):
        return SimpleNamespace(hard_filter_passed=True, total_score=92.0)


def _source():
    return DiscoverySourceSummary(
        id=uuid4(), company="Acme", provider=DiscoveryProvider.GREENHOUSE,
        board_identifier="acme", enabled=True, priority=100, config={},
        created_at=datetime.now(timezone.utc),
    )


def test_title_prefilter_is_security_broad_but_rejects_unrelated_roles():
    f = SecurityTitlePrefilter(["Principal Application Security Engineer"])
    assert f.evaluate("Head of AI Security").accepted
    assert f.evaluate("Principal Product Security Engineer").accepted
    assert not f.evaluate("Senior Accountant").accepted
    assert not f.evaluate("Security Guard").accepted


def test_discovery_run_ingests_and_analyzes_only_security_title_candidates():
    source = _source()
    repo = FakeDiscoveryRepo(source)
    service = DiscoveryService(
        discovery_repo=repo, policy_repo=FakePolicyRepo(), ingestion_service=FakeIngestion(),
        match_service=FakeMatcher(), adapters=FakeRegistry(),
    )
    result = service.run(DiscoveryRunRequest(source_id=source.id, minimum_surface_score=80))
    assert result.totals["postings_retrieved"] == 2
    assert result.totals["title_candidates"] == 1
    assert result.totals["jobs_created"] == 1
    assert result.totals["jobs_analyzed"] == 1
    assert result.totals["hard_filter_passed"] == 1
    assert result.totals["surfaced"] == 1
    assert result.totals["postings_closed"] == 2
    assert result.runs[0].status is DiscoveryRunStatus.COMPLETED
    assert len(repo.links) == 1
