from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from job_agent.domain.discovery import (
    DiscoveryBatchResponse,
    DiscoveryProvider,
    DiscoveryRunRequest,
    DiscoveryRunStatus,
    DiscoveryRunSummary,
    DiscoverySourceSummary,
)
from job_agent.domain.jobs import JobIngestRequest, JobMatchRequest, WorkArrangement
from job_agent.repositories.interfaces import DiscoveryRepository, PolicyRepository
from job_agent.services.discovery_adapters import AdapterRegistry
from job_agent.services.job_matching import JobIngestionService, JobMatchService


_SECURITY_TITLE_TERMS = (
    "security",
    "appsec",
    "application security",
    "product security",
    "cybersecurity",
    "cyber security",
    "information security",
    "infosec",
    "red team",
    "offensive",
    "vulnerability",
    "threat",
    "trust security",
)

_STRONG_EXCLUSION_TERMS = (
    "security guard",
    "physical security officer",
    "loss prevention",
    "public safety",
)


@dataclass(frozen=True)
class TitlePrefilterDecision:
    accepted: bool
    rationale: str


class SecurityTitlePrefilter:
    def __init__(self, target_titles: list[str] | None = None) -> None:
        self.target_titles = [title.lower().strip() for title in (target_titles or []) if title.strip()]

    def evaluate(self, title: str) -> TitlePrefilterDecision:
        lower = re.sub(r"\s+", " ", title.lower()).strip()
        if any(term in lower for term in _STRONG_EXCLUSION_TERMS):
            return TitlePrefilterDecision(False, "explicit non-cyber security title")
        if any(term in lower for term in _SECURITY_TITLE_TERMS):
            return TitlePrefilterDecision(True, "security-family title")
        if any(self._title_overlap(lower, target) for target in self.target_titles):
            return TitlePrefilterDecision(True, "overlaps configured target title")
        return TitlePrefilterDecision(False, "no security-title signal")

    @staticmethod
    def _title_overlap(candidate: str, target: str) -> bool:
        stop = {"of", "and", "the", "senior", "sr", "lead", "staff", "principal", "manager", "director", "head"}
        candidate_tokens = {token for token in re.findall(r"[a-z0-9]+", candidate) if token not in stop}
        target_tokens = {token for token in re.findall(r"[a-z0-9]+", target) if token not in stop}
        return bool(candidate_tokens and target_tokens and len(candidate_tokens & target_tokens) >= 2)


class DiscoveryService:
    def __init__(
        self,
        *,
        discovery_repo: DiscoveryRepository,
        policy_repo: PolicyRepository,
        ingestion_service: JobIngestionService,
        match_service: JobMatchService,
        adapters: AdapterRegistry | None = None,
    ) -> None:
        self.discovery_repo = discovery_repo
        self.policy_repo = policy_repo
        self.ingestion_service = ingestion_service
        self.match_service = match_service
        self.adapters = adapters or AdapterRegistry()

    def run(self, request: DiscoveryRunRequest) -> DiscoveryBatchResponse:
        if request.source_id:
            source = self.discovery_repo.get_source(request.source_id)
            if source is None:
                raise LookupError("discovery source not found")
            sources = [source]
        else:
            sources = self.discovery_repo.list_sources(enabled_only=not request.include_disabled)

        active_policy = self.policy_repo.get_active()
        if request.analyze and active_policy is None:
            raise LookupError("targeting policy not found; create or activate a policy first")
        prefilter = SecurityTitlePrefilter(active_policy.target_titles if active_policy else [])

        summaries = [self._run_source(source, request, prefilter) for source in sources]
        fields = (
            "postings_retrieved",
            "title_candidates",
            "jobs_created",
            "jobs_updated",
            "jobs_analyzed",
            "hard_filter_passed",
            "surfaced",
            "postings_closed",
        )
        totals = {field: sum(getattr(summary, field) for summary in summaries) for field in fields}
        return DiscoveryBatchResponse(runs=summaries, totals=totals)

    @staticmethod
    def _work_arrangement(value: str | None) -> WorkArrangement | None:
        if not value:
            return None
        normalized = value.strip().lower().replace("-", "")
        if normalized in {"remote"}:
            return WorkArrangement.REMOTE
        if normalized in {"hybrid"}:
            return WorkArrangement.HYBRID
        if normalized in {"onsite", "onsite"}:
            return WorkArrangement.ONSITE
        return None

    def _run_source(
        self,
        source: DiscoverySourceSummary,
        request: DiscoveryRunRequest,
        prefilter: SecurityTitlePrefilter,
    ) -> DiscoveryRunSummary:
        started = datetime.now(timezone.utc)
        run_id = self.discovery_repo.start_run(source.id, started)
        counters = {
            "postings_retrieved": 0,
            "title_candidates": 0,
            "jobs_created": 0,
            "jobs_updated": 0,
            "jobs_analyzed": 0,
            "hard_filter_passed": 0,
            "surfaced": 0,
            "postings_closed": 0,
        }
        seen_external_ids: set[str] = set()
        errors: list[str] = []

        try:
            adapter = self.adapters.get(source.provider)
            postings = adapter.fetch(source)
            counters["postings_retrieved"] = len(postings)

            for posting in postings:
                seen_external_ids.add(posting.external_id)
                decision = prefilter.evaluate(posting.title)
                if not decision.accepted:
                    continue
                counters["title_candidates"] += 1

                source_key = f"{source.provider.value}:{source.board_identifier}"
                try:
                    ingest = self.ingestion_service.ingest(
                        JobIngestRequest(
                            source=source_key,
                            external_id=posting.external_id,
                            source_url=posting.source_url,
                            company=source.company,
                            title=posting.title,
                            location=posting.location,
                            compensation_text=posting.compensation_text,
                            work_arrangement=self._work_arrangement(posting.work_arrangement),
                            description_raw=posting.description_raw,
                        )
                    )
                    self.discovery_repo.link_job(
                        job_id=ingest.job_id,
                        source_id=source.id,
                        seen_at=datetime.now(timezone.utc),
                    )
                    if ingest.created:
                        counters["jobs_created"] += 1
                    else:
                        counters["jobs_updated"] += 1

                    if request.analyze:
                        match = self.match_service.analyze(ingest.job_id, JobMatchRequest())
                        counters["jobs_analyzed"] += 1
                        if match.hard_filter_passed:
                            counters["hard_filter_passed"] += 1
                            if match.total_score >= request.minimum_surface_score:
                                counters["surfaced"] += 1
                except Exception as exc:  # isolate malformed postings instead of aborting board scan
                    errors.append(f"{posting.external_id}: processing failed: {exc}")

            counters["postings_closed"] = self.discovery_repo.mark_unseen_closed(
                source_id=source.id,
                seen_external_ids=seen_external_ids,
                seen_at=started,
            )
            completed = datetime.now(timezone.utc)
            status = DiscoveryRunStatus.PARTIAL if errors else DiscoveryRunStatus.COMPLETED
            error_message = " | ".join(errors[:10]) if errors else None
        except Exception as exc:
            completed = datetime.now(timezone.utc)
            status = DiscoveryRunStatus.FAILED
            error_message = str(exc)

        summary = self.discovery_repo.finish_run(
            run_id=run_id,
            completed_at=completed,
            status=status,
            counters=counters,
            error_message=error_message,
        )
        self.discovery_repo.touch_source(source.id, completed)
        return summary
