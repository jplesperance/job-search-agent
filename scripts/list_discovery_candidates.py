from __future__ import annotations

import argparse

from job_agent.db.session import get_session_factory
from job_agent.repositories.sqlalchemy import SqlAlchemyDiscoveryRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="List currently open discovered jobs that passed policy filters")
    parser.add_argument("--minimum-score", type=float, default=80.0)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--include-closed", action="store_true")
    args = parser.parse_args()

    with get_session_factory()() as session:
        items = SqlAlchemyDiscoveryRepository(session).list_candidates(
            minimum_score=args.minimum_score,
            limit=args.limit,
            open_only=not args.include_closed,
        )

    if not items:
        print("No surfaced candidates found.")
        return
    for item in items:
        print(f"{item.total_score:6.2f}  {item.company} — {item.title}")
        print(f"        {item.location or 'location unavailable'} | {item.compensation_text or 'salary unavailable'}")
        print(f"        job_id={item.job_id}")
        if item.source_url:
            print(f"        {item.source_url}")
        if item.gaps:
            print(f"        gaps: {'; '.join(item.gaps[:3])}")


if __name__ == "__main__":
    main()
