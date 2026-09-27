from __future__ import annotations

import argparse

from job_agent.config.settings import get_settings
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
from job_agent.services.notifications import NotificationService, build_notifier


def build_discovery(session) -> tuple[DiscoveryService, SqlAlchemyDiscoveryRepository]:
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
            evidence_search=EvidenceSearchService(
                evidence_repo=evidence,
                career_repo=career,
            ),
        ),
        adapters=AdapterRegistry(),
    )
    return service, discovery


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Phase 4.1 scheduled discovery and notify on new canonical matches"
    )
    parser.add_argument("--minimum-score", type=float)
    parser.add_argument(
        "--bootstrap-suppress-existing",
        action="store_true",
        help="Create suppressed notification state for current matches instead of sending them.",
    )
    args = parser.parse_args()

    settings = get_settings()
    minimum_score = (
        args.minimum_score
        if args.minimum_score is not None
        else settings.scheduled_discovery_minimum_score
    )

    # Discovery is committed before delivery attempts, so a notification failure
    # can never roll back a successful ATS poll or job analysis.
    with get_session_factory()() as session:
        service, _ = build_discovery(session)
        result = service.run(
            DiscoveryRunRequest(
                analyze=True,
                minimum_surface_score=minimum_score,
                include_disabled=False,
            )
        )
        session.commit()

    print("Discovery totals:")
    for key, value in result.totals.items():
        print(f"  {key:22} {value}")

    notifier = build_notifier(settings)
    if notifier is None:
        print("Notifications disabled; discovery completed.")
        return

    sent = skipped = failed = 0
    with get_session_factory()() as session:
        _, discovery = build_discovery(session)
        candidates = discovery.list_candidates(
            minimum_score=minimum_score,
            limit=10_000,
            open_only=True,
        )
        notifications = NotificationService(
            session,
            notifier,
            max_attempts=settings.notification_max_attempts,
        )
        for candidate in candidates:
            if args.bootstrap_suppress_existing:
                result_item = notifications.suppress(candidate)
            else:
                result_item = notifications.notify(candidate)
            if result_item.status.value == "sent" and result_item.attempted:
                sent += 1
            elif result_item.status.value == "failed" and result_item.attempted:
                failed += 1
            else:
                skipped += 1
        session.commit()

    print(f"Notifications: sent={sent} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()
