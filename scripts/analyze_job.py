#!/usr/bin/env python3
from __future__ import annotations

import argparse
from uuid import UUID

from job_agent.db.session import get_session_factory
from job_agent.domain.jobs import JobMatchRequest
from job_agent.repositories.sqlalchemy import (
    SqlAlchemyCareerRepository,
    SqlAlchemyEvidenceRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyPolicyRepository,
)
from job_agent.services.evidence_search import EvidenceSearchService
from job_agent.services.job_matching import JobMatchService


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze an ingested job against verified career evidence")
    parser.add_argument("job_id", type=UUID)
    parser.add_argument("--policy-id", type=UUID)
    parser.add_argument("--include-internal-evidence", action="store_true")
    parser.add_argument("--max-evidence", type=int, default=3)
    args = parser.parse_args()

    with get_session_factory()() as session:
        career = SqlAlchemyCareerRepository(session)
        evidence = SqlAlchemyEvidenceRepository(session)
        service = JobMatchService(
            job_repo=SqlAlchemyJobRepository(session),
            policy_repo=SqlAlchemyPolicyRepository(session),
            career_repo=career,
            evidence_search=EvidenceSearchService(evidence_repo=evidence, career_repo=career),
        )
        try:
            result = service.analyze(
                args.job_id,
                JobMatchRequest(
                    policy_id=args.policy_id,
                    resume_safe_only=not args.include_internal_evidence,
                    max_evidence_per_requirement=args.max_evidence,
                ),
            )
            session.commit()
        except Exception:
            session.rollback()
            raise

    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
