#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from job_agent.db.tables import (
    CareerProfileRow,
    CertificationRow,
    EvidenceItemRow,
    EvidenceSkillRow,
    ExperienceRow,
    SkillRow,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = ROOT / "data" / "knowledge_base" / "v1" / "postgres_compat_seed.json"


def parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def load_seed(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def import_seed(session: Session, seed: dict) -> None:
    for row in seed["career_profiles"]:
        obj = CareerProfileRow(
            id=UUID(row["id"]),
            display_name=row["display_name"],
            professional_headline=row.get("professional_headline"),
            summary=row.get("summary"),
        )
        session.merge(obj)

    for row in seed["experiences"]:
        obj = ExperienceRow(
            id=UUID(row["id"]),
            profile_id=UUID(row["profile_id"]),
            employer=row["employer"],
            title=row["title"],
            start_date=parse_date(row["start_date"]),
            end_date=parse_date(row.get("end_date")),
            location=row.get("location"),
            description=row.get("description"),
        )
        session.merge(obj)

    for row in seed["skills"]:
        obj = SkillRow(
            id=UUID(row["id"]),
            name=row["name"],
            category=row.get("category"),
            aliases=row.get("aliases", []),
        )
        session.merge(obj)

    for row in seed["evidence_items"]:
        obj = EvidenceItemRow(
            id=UUID(row["id"]),
            experience_id=UUID(row["experience_id"]) if row.get("experience_id") else None,
            category=row["category"],
            claim=row["claim"],
            context=row.get("context"),
            metric=row.get("metric"),
            provenance=row.get("provenance"),
            approval_status=row.get("approval_status", "draft"),
            tags=row.get("tags", []),
        )
        session.merge(obj)

    for row in seed["certifications"]:
        obj = CertificationRow(
            id=UUID(row["id"]),
            profile_id=UUID(row["profile_id"]),
            name=row["name"],
            issuer=row["issuer"],
            issued_on=parse_date(row.get("issued_on")),
            expires_on=parse_date(row.get("expires_on")),
            credential_id=row.get("credential_id"),
            approval_status=row.get("approval_status", "approved"),
        )
        session.merge(obj)

    session.flush()

    # Rebuild evidence<->skill mappings from the deterministic seed.
    evidence_ids = [UUID(row["id"]) for row in seed["evidence_items"]]
    if evidence_ids:
        session.query(EvidenceSkillRow).filter(
            EvidenceSkillRow.evidence_id.in_(evidence_ids)
        ).delete(synchronize_session=False)
    for row in seed["evidence_skills"]:
        session.add(
            EvidenceSkillRow(
                evidence_id=UUID(row["evidence_id"]),
                skill_id=UUID(row["skill_id"]),
            )
        )
    session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Career Knowledge Base v1 into PostgreSQL")
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--dry-run", action="store_true", help="Validate/parse seed without writing to the database")
    args = parser.parse_args()

    seed = load_seed(args.seed)
    print(
        f"Seed parsed: {len(seed['experiences'])} experiences, "
        f"{len(seed['evidence_items'])} evidence items, {len(seed['skills'])} skills"
    )
    if args.dry_run:
        return

    from job_agent.db.session import SessionLocal

    with SessionLocal() as session:
        import_seed(session, seed)
    print("Knowledge base import complete")


if __name__ == "__main__":
    main()
