from __future__ import annotations

import argparse

from job_agent.db.session import get_session_factory
from job_agent.domain.discovery import DiscoveryProvider, DiscoverySourceCreate
from job_agent.repositories.sqlalchemy import SqlAlchemyDiscoveryRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Add or update a public ATS discovery source")
    parser.add_argument("--company", required=True)
    parser.add_argument("--provider", required=True, choices=[p.value for p in DiscoveryProvider])
    parser.add_argument("--identifier", required=True, help="Greenhouse board token, Lever site, or Ashby board name")
    parser.add_argument("--priority", type=int, default=100)
    parser.add_argument("--disabled", action="store_true")
    parser.add_argument("--lever-region", choices=["global", "eu"], default="global")
    args = parser.parse_args()

    config: dict[str, object] = {}
    if args.provider == DiscoveryProvider.LEVER.value:
        config["region"] = args.lever_region

    request = DiscoverySourceCreate(
        company=args.company,
        provider=DiscoveryProvider(args.provider),
        board_identifier=args.identifier,
        enabled=not args.disabled,
        priority=args.priority,
        config=config,
    )
    with get_session_factory()() as session:
        repo = SqlAlchemyDiscoveryRepository(session)
        source = repo.add_source(request)
        session.commit()
    print(source.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
