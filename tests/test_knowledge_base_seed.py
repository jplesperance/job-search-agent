from pathlib import Path

from job_agent.knowledge_base.validator import load_knowledge_base, validate_knowledge_base


ROOT = Path(__file__).resolve().parents[1]
KB_PATH = ROOT / "data" / "knowledge_base" / "v1" / "knowledge_base.json"


def test_seed_knowledge_base_is_valid():
    kb = load_knowledge_base(KB_PATH)
    assert validate_knowledge_base(kb) == []


def test_seed_has_expected_minimum_depth():
    kb = load_knowledge_base(KB_PATH)
    assert len(kb["experiences"]) >= 15
    assert len(kb["evidence_items"]) >= 150
    assert sum(x["verification_status"] == "USER_VERIFIED" for x in kb["evidence_items"]) >= 140


def test_hard_career_corrections_are_encoded():
    kb = load_knowledge_base(KB_PATH)
    experiences = {x["canonical_key"]: x for x in kb["experiences"]}
    assert experiences["wiscasset-2000-2006"]["attributes"]["business_owner"] is False
    assert experiences["hilton-romack-2024-2025"]["attributes"]["people_management"] is False


def test_v1_1_corrections_are_encoded():
    kb = load_knowledge_base(KB_PATH)
    canonical_keys = {x["canonical_key"] for x in kb["experiences"]}
    assert "cionsystems-advisor-2020" not in canonical_keys
    assert "cuemby-advisor-2020" not in canonical_keys

    technologies = {x["name"] for x in kb["technologies"]}
    assert "Checkmarx" in technologies
    assert "CrowdStrike" not in technologies

    frameworks = {x["name"] for x in kb["frameworks"]}
    assert "HIPAA" in frameworks
    assert "HITRUST" in frameworks
    assert all("HIPAA High Trust" not in name for name in frameworks)

    evidence_by_key = {x["evidence_key"]: x for x in kb["evidence_items"]}
    assert "Checkmarx" in evidence_by_key["HLT-TOOLS-004"]["claim"]
    assert "HIPAA" in evidence_by_key["APX-COMP-001"]["claim"]
    assert "HITRUST" in evidence_by_key["APX-COMP-001"]["claim"]
    assert "RIC-COMP-001" in evidence_by_key
