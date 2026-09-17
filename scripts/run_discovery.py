from __future__ import annotations

import argparse
from uuid import UUID

from job_agent.db.session import get_session_factory
from job_agent.domain.discovery import DiscoveryRunRequest
from job_agent.repositories.sqlalchemy import (
    SqlAlchemyCareerRepository,
    SqlAlchemyDiscoveryRepository,
    SqlAlchemyEvidenceRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyPolicyRepository,
)
from job_agent.services.discovery import DiscoveryService
from job_agent.services.discovery_adapters import AdapterRegistry
from job_agent.services.evidence_search import EvidenceSearchService
from job_agent.services.job_matching import JobIngestionService, JobMatchService


def main() -> None:
    parser = argparse.ArgumentParser(description="Poll configured ATS boards and analyze security jobs")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true")
    group.add_argument("--source-id", type=UUID)
    parser.add_argument("--no-analyze", action="store_true")
    parser.add_argument("--minimum-score", type=float, default=80.0)
    parser.add_argument("--include-disabled", action="store_true")
    args = parser.parse_args()

    with get_session_factory()() as session:
        career = SqlAlchemyCareerRepository(session)
        evidence = SqlAlchemyEvidenceRepository(session)
        jobs = SqlAlchemyJobRepository(session)
        policies = SqlAlchemyPolicyRepository(session)
        discovery = SqlAlchemyDiscoveryRepository(session)
        service = DiscoveryService(
            discovery_repo=discovery,
            policy_repo=policies,
            ingestion_service=JobIngestionService(job_repo=jobs, career_repo=career),
            match_service=JobMatchService(
                job_repo=jobs,
                policy_repo=policies,
                career_repo=career,
                evidence_search=EvidenceSearchService(evidence_repo=evidence, career_repo=career),
            ),
            adapters=AdapterRegistry(),
        )
        result = service.run(
            DiscoveryRunRequest(
                source_id=args.source_id,
                analyze=not args.no_analyze,
                minimum_surface_score=args.minimum_score,
                include_disabled=args.include_disabled,
            )
        )
        session.commit()

    for run in result.runs:
        print(
            f"{run.company} [{run.provider.value}] {run.status.value}: "
            f"retrieved={run.postings_retrieved} candidates={run.title_candidates} "
            f"new={run.jobs_created} updated={run.jobs_updated} analyzed={run.jobs_analyzed} "
            f"hard_pass={run.hard_filter_passed} surfaced={run.surfaced} closed={run.postings_closed}"
        )
        if run.error_message:
            print(f"  error: {run.error_message}")
    print("Totals:")
    for key, value in result.totals.items():
        print(f"  {key:22} {value}")


if __name__ == "__main__":
    main()
