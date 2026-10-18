#!/usr/bin/env python3
"""Analyze a job URL, or supply a pasted description for protected/JS-only pages."""
from __future__ import annotations

import argparse
from pathlib import Path

from job_agent.db.session import get_session_factory
from job_agent.domain.manual_intake import ManualJobIntakeRequest
from job_agent.repositories.sqlalchemy import (
    SqlAlchemyCareerRepository, SqlAlchemyEvidenceRepository,
    SqlAlchemyJobRepository, SqlAlchemyPolicyRepository,
)
from job_agent.services.evidence_search import EvidenceSearchService
from job_agent.services.job_matching import JobIngestionService, JobMatchService
from job_agent.services.manual_job_intake import ManualJobIntakeService
from job_agent.services.manual_job_fetch import ManualFetchError


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual job intake with immediate evidence-grounded analysis")
    parser.add_argument("url", nargs="?", help="Public HTTPS posting URL")
    parser.add_argument("--text-file", type=Path, help="Text fallback; bypasses URL fetch")
    parser.add_argument("--company", help="Required if the page does not provide a company")
    parser.add_argument("--title", help="Required if the page does not provide a job title")
    parser.add_argument("--location")
    parser.add_argument("--compensation")
    parser.add_argument("--work-arrangement", choices=["remote", "hybrid", "onsite", "unknown"])
    args = parser.parse_args()
    if not args.url and not args.text_file:
        parser.error("Provide a URL or --text-file")
    request = ManualJobIntakeRequest(
        source_url=args.url,
        description_raw=args.text_file.read_text(encoding="utf-8") if args.text_file else None,
        company=args.company, title=args.title, location=args.location,
        compensation_text=args.compensation, work_arrangement=args.work_arrangement,
    )
    with get_session_factory()() as session:
        career = SqlAlchemyCareerRepository(session)
        evidence = SqlAlchemyEvidenceRepository(session)
        jobs = SqlAlchemyJobRepository(session)
        service = ManualJobIntakeService(
            session=session,
            ingestion=JobIngestionService(job_repo=jobs, career_repo=career),
            matcher=JobMatchService(
                job_repo=jobs, policy_repo=SqlAlchemyPolicyRepository(session),
                career_repo=career,
                evidence_search=EvidenceSearchService(evidence_repo=evidence, career_repo=career),
            ),
        )
        try:
            result = service.submit(request)
            session.commit()
        except (ManualFetchError, LookupError) as exc:
            session.rollback()
            parser.exit(2, f"Manual intake unsuccessful: {exc}\n")
        except Exception:
            session.rollback()
            raise
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
