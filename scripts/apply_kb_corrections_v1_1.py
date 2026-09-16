#!/usr/bin/env python3
from __future__ import annotations

import argparse
from uuid import UUID

from job_agent.db.tables import ExperienceRow
from import_knowledge_base import DEFAULT_SEED, import_seed, load_seed

REMOVED_EXPERIENCE_IDS = (
    UUID("78b31fbf-75c2-550c-b175-7b4a8ae28f17"),  # CionSystems
    UUID("6379e382-92fd-53fa-82fd-0d8bd3b05a00"),  # Cuemby
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply Career Knowledge Base v1.1 corrections to an existing v1 PostgreSQL database"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    seed = load_seed(DEFAULT_SEED)
    print(
        f"Corrected seed: {len(seed['experiences'])} experiences, "
        f"{len(seed['evidence_items'])} evidence items, {len(seed['skills'])} skills"
    )
    print("Will remove canonical advisory roles: CionSystems, Cuemby")
    print("Will correct Hilton SAST tooling: CrowdStrike -> Checkmarx")
    print("Will normalize compliance terminology: HIPAA + HITRUST")
    print("Will add Ricoh HIPAA/HITRUST evidence")
    if args.dry_run:
        return

    from job_agent.db.session import SessionLocal

    with SessionLocal() as session:
        for experience_id in REMOVED_EXPERIENCE_IDS:
            obj = session.get(ExperienceRow, experience_id)
            if obj is not None:
                session.delete(obj)
        session.flush()
        # import_seed performs deterministic upserts and commits the transaction.
        import_seed(session, seed)

    print("Career Knowledge Base v1.1 corrections applied")


if __name__ == "__main__":
    main()
