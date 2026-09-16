import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "knowledge_base" / "v1" / "postgres_compat_seed.json"


def test_postgres_seed_contains_retrieval_metadata():
    seed = json.loads(SEED.read_text())
    evidence = seed["evidence_items"]
    experiences = seed["experiences"]

    assert len(evidence) == 252
    assert all(item.get("evidence_key") for item in evidence)
    assert len({item["evidence_key"] for item in evidence}) == len(evidence)
    assert all(item.get("verification_status") for item in evidence)
    assert all("resume_eligible" in item for item in evidence)
    assert all(item.get("resume_visibility") for item in evidence)

    assert len(experiences) == 18
    assert all(item.get("canonical_key") for item in experiences)
    assert all(item.get("verification_status") for item in experiences)
