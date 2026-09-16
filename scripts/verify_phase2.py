#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select

from job_agent.db.session import get_session_factory
from job_agent.db.tables import EvidenceItemRow, ExperienceRow

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "knowledge_base" / "v1" / "postgres_compat_seed.json"


def main() -> None:
    seed = json.loads(SEED.read_text())
    evidence_ids = [UUID(item["id"]) for item in seed["evidence_items"]]
    experience_ids = [UUID(item["id"]) for item in seed["experiences"]]

    with get_session_factory()() as session:
        evidence_total = session.scalar(
            select(func.count()).select_from(EvidenceItemRow).where(EvidenceItemRow.id.in_(evidence_ids))
        )
        evidence_keys = session.scalar(
            select(func.count(EvidenceItemRow.evidence_key)).where(EvidenceItemRow.id.in_(evidence_ids))
        )
        verification = session.scalar(
            select(func.count(EvidenceItemRow.verification_status)).where(
                EvidenceItemRow.id.in_(evidence_ids)
            )
        )
        resume_eligible = session.scalar(
            select(func.count()).select_from(EvidenceItemRow).where(
                EvidenceItemRow.id.in_(evidence_ids), EvidenceItemRow.resume_eligible.is_(True)
            )
        )
        experience_total = session.scalar(
            select(func.count()).select_from(ExperienceRow).where(ExperienceRow.id.in_(experience_ids))
        )
        experience_keys = session.scalar(
            select(func.count(ExperienceRow.canonical_key)).where(ExperienceRow.id.in_(experience_ids))
        )

    expected_evidence = len(evidence_ids)
    expected_experiences = len(experience_ids)
    expected_resume_eligible = sum(bool(item.get("resume_eligible")) for item in seed["evidence_items"])

    print(f"seed experiences found      {experience_total}/{expected_experiences}")
    print(f"experience canonical keys   {experience_keys}/{expected_experiences}")
    print(f"seed evidence found         {evidence_total}/{expected_evidence}")
    print(f"evidence stable keys        {evidence_keys}/{expected_evidence}")
    print(f"verification metadata       {verification}/{expected_evidence}")
    print(f"resume eligible             {resume_eligible}/{expected_resume_eligible}")

    ok = all(
        [
            experience_total == expected_experiences,
            experience_keys == expected_experiences,
            evidence_total == expected_evidence,
            evidence_keys == expected_evidence,
            verification == expected_evidence,
            resume_eligible == expected_resume_eligible,
        ]
    )
    if not ok:
        raise SystemExit("Phase 2 metadata verification failed")
    print("Phase 2 retrieval metadata verified")


if __name__ == "__main__":
    main()
