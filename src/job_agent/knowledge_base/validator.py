from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class KnowledgeBaseValidationError(ValueError):
    pass


def load_knowledge_base(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def validate_knowledge_base(kb: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {"schema_version", "dataset_version", "profile", "experiences", "evidence_items"}
    missing = required - kb.keys()
    if missing:
        errors.append(f"Missing top-level keys: {sorted(missing)}")
        return errors

    experiences = kb["experiences"]
    evidence = kb["evidence_items"]
    exp_ids = {x["id"] for x in experiences}
    ev_ids = [x["id"] for x in evidence]
    ev_keys = [x["evidence_key"] for x in evidence]

    if len(ev_ids) != len(set(ev_ids)):
        errors.append("Duplicate evidence UUIDs found")
    if len(ev_keys) != len(set(ev_keys)):
        errors.append("Duplicate evidence keys found")

    for item in evidence:
        if item.get("experience_id") and item["experience_id"] not in exp_ids:
            errors.append(f"Evidence {item['evidence_key']} references unknown experience")
        if item["verification_status"] == "NEEDS_VERIFICATION" and item["approval_status"] == "approved":
            errors.append(f"Unverified evidence {item['evidence_key']} cannot be approved")
        if item["resume_visibility"] == "internal_only" and item["resume_eligible"]:
            errors.append(f"Internal-only evidence {item['evidence_key']} cannot be resume eligible")

    # Hard factual/correction guardrails.
    wiscasset = next((x for x in experiences if x["canonical_key"] == "wiscasset-2000-2006"), None)
    if not wiscasset or wiscasset.get("attributes", {}).get("business_owner") is not False:
        errors.append("Wiscasset business_owner must be false")
    hilton = next((x for x in experiences if x["canonical_key"] == "hilton-romack-2024-2025"), None)
    if not hilton or hilton.get("attributes", {}).get("people_management") is not False:
        errors.append("Hilton people_management must be false")
    if any(x["canonical_key"] in {"cionsystems-advisor-2020", "cuemby-advisor-2020"} for x in experiences):
        errors.append("Removed CionSystems/Cuemby advisory roles must not be present")
    technology_names = {x["name"] for x in kb.get("technologies", [])}
    if "CrowdStrike" in technology_names or "Checkmarx" not in technology_names:
        errors.append("Hilton SAST technology correction must be Checkmarx, not CrowdStrike")
    framework_names = {x["name"] for x in kb.get("frameworks", [])}
    if "HIPAA" not in framework_names or "HITRUST" not in framework_names:
        errors.append("HIPAA and HITRUST must be represented as separate frameworks")
    if any("HIPAA High Trust" in x["name"] for x in kb.get("frameworks", [])):
        errors.append("Deprecated HIPAA High Trust label must not be present")

    # Validate relationship mappings.
    skill_ids = {x["id"] for x in kb.get("skills", [])}
    tech_ids = {x["id"] for x in kb.get("technologies", [])}
    fw_ids = {x["id"] for x in kb.get("frameworks", [])}
    evid_set = set(ev_ids)
    for m in kb.get("evidence_skill_mappings", []):
        if m["evidence_id"] not in evid_set or m["skill_id"] not in skill_ids:
            errors.append("Invalid evidence_skill mapping")
    for m in kb.get("evidence_technology_mappings", []):
        if m["evidence_id"] not in evid_set or m["technology_id"] not in tech_ids:
            errors.append("Invalid evidence_technology mapping")
    for m in kb.get("evidence_framework_mappings", []):
        if m["evidence_id"] not in evid_set or m["framework_id"] not in fw_ids:
            errors.append("Invalid evidence_framework mapping")
    return errors


def assert_valid_knowledge_base(kb: dict[str, Any]) -> None:
    errors = validate_knowledge_base(kb)
    if errors:
        raise KnowledgeBaseValidationError("; ".join(errors))
