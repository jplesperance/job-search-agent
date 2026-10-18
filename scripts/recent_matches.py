"""List currently qualifying jobs first discovered within a recent window."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from job_agent.db.session import get_session_factory
from job_agent.db.tables import JobOpportunityRow, JobSourcePostingRow, NotificationStateRow
from job_agent.repositories.sqlalchemy import SqlAlchemyDiscoveryRepository
from sqlalchemy import select


def main() -> None:
    parser = argparse.ArgumentParser(description="Recent qualified discoveries")
    parser.add_argument("--hours", type=int, default=72)
    parser.add_argument("--minimum-score", type=float, default=80.0)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(args.hours, 1))
    with get_session_factory()() as session:
        repo = SqlAlchemyDiscoveryRepository(session)
        items = repo.list_candidates(minimum_score=args.minimum_score, limit=10000, open_only=True)
        count = 0
        for candidate in items:
            row = session.get(JobOpportunityRow, candidate.job_id)
            if row is None or row.discovered_at < cutoff:
                continue
            sources = list(session.execute(
                select(JobSourcePostingRow.source)
                .where(JobSourcePostingRow.job_id == candidate.job_id)
                .distinct()
            ).scalars())
            notification = session.execute(
                select(NotificationStateRow.status)
                .where(NotificationStateRow.job_id == candidate.job_id, NotificationStateRow.channel == "pushover", NotificationStateRow.notification_type == "new_match")
                .limit(1)
            ).scalar_one_or_none()
            print(f"{candidate.total_score:.1f}  {candidate.company} — {candidate.title}")
            print(f"    {candidate.location or 'Location unknown'} | {candidate.compensation_text or 'Salary unknown'}")
            print(f"    first_seen={row.discovered_at.isoformat()} sources={', '.join(sources)} push={notification or 'not_queued'}")
            if candidate.source_url:
                print(f"    {candidate.source_url}")
            count += 1
            if count >= max(args.limit, 1):
                break
        if not count:
            print("No recently discovered qualifying jobs in this window.")


if __name__ == "__main__":
    main()
