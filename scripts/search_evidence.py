#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from job_agent.db.session import get_session_factory
from job_agent.domain.retrieval import EvidenceSearchRequest, MatchMode, RetrievalScope
from job_agent.repositories.sqlalchemy import SqlAlchemyCareerRepository, SqlAlchemyEvidenceRepository
from job_agent.services.evidence_search import EvidenceSearchService


def main() -> None:
    parser = argparse.ArgumentParser(description="Search verified career evidence in PostgreSQL")
    parser.add_argument("--query", help="Free-text query")
    parser.add_argument("--skill", action="append", default=[], help="Skill name; repeatable")
    parser.add_argument("--scope", choices=[s.value for s in RetrievalScope], default="general")
    parser.add_argument("--match-mode", choices=[m.value for m in MatchMode], default="any")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--json", action="store_true", help="Emit the complete JSON response")
    args = parser.parse_args()

    request = EvidenceSearchRequest(
        query=args.query,
        skills=args.skill,
        scope=RetrievalScope(args.scope),
        match_mode=MatchMode(args.match_mode),
        limit=args.limit,
    )

    with get_session_factory()() as session:
        service = EvidenceSearchService(
            evidence_repo=SqlAlchemyEvidenceRepository(session),
            career_repo=SqlAlchemyCareerRepository(session),
        )
        response = service.search(request)

    if args.json:
        print(response.model_dump_json(indent=2))
        return

    if response.unknown_skills:
        print("Unknown skill terms: " + ", ".join(response.unknown_skills))
    print(f"Results: {response.count}")
    for result in response.results:
        print(
            f"{result.score:6.2f}  {result.evidence_key or result.evidence_id}  "
            f"{result.employer or '-'} / {result.title or '-'}"
        )
        print(f"        {result.claim}")
        if result.matched_skills:
            print("        matched: " + ", ".join(result.matched_skills))


if __name__ == "__main__":
    main()
