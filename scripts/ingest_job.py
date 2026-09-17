#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from job_agent.db.session import get_session_factory
from job_agent.domain.jobs import JobIngestRequest
from job_agent.repositories.sqlalchemy import SqlAlchemyCareerRepository, SqlAlchemyJobRepository
from job_agent.services.job_matching import JobIngestionService


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest and deterministically parse a job description")
    parser.add_argument("job_file", type=Path, help="Plain-text job description")
    parser.add_argument("--company", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--location")
    parser.add_argument("--compensation")
    parser.add_argument("--source", default="manual")
    parser.add_argument("--external-id")
    parser.add_argument("--source-url")
    args = parser.parse_args()

    request = JobIngestRequest(
        source=args.source,
        external_id=args.external_id,
        source_url=args.source_url,
        company=args.company,
        title=args.title,
        location=args.location,
        compensation_text=args.compensation,
        description_raw=args.job_file.read_text(),
    )

    with get_session_factory()() as session:
        service = JobIngestionService(
            job_repo=SqlAlchemyJobRepository(session),
            career_repo=SqlAlchemyCareerRepository(session),
        )
        try:
            result = service.ingest(request)
            session.commit()
        except Exception:
            session.rollback()
            raise

    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
