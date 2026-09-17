from __future__ import annotations

import argparse
import json
from pathlib import Path

from job_agent.db.session import get_session_factory
from job_agent.domain.discovery import DiscoverySourceCreate
from job_agent.repositories.sqlalchemy import SqlAlchemyDiscoveryRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Load discovery sources from a JSON array")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.path.read_text())
    if not isinstance(payload, list):
        raise SystemExit("Source file must contain a JSON array")

    created = []
    with get_session_factory()() as session:
        repo = SqlAlchemyDiscoveryRepository(session)
        for item in payload:
            source = repo.add_source(DiscoverySourceCreate.model_validate(item))
            created.append(source)
        session.commit()

    print(f"Loaded {len(created)} discovery sources")
    for source in created:
        print(f"{source.id}  {source.provider.value:10} {source.company} [{source.board_identifier}]")


if __name__ == "__main__":
    main()
