#!/usr/bin/env python3
from pathlib import Path

from job_agent.knowledge_base.validator import assert_valid_knowledge_base, load_knowledge_base

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "data" / "knowledge_base" / "v1" / "knowledge_base.json"
kb = load_knowledge_base(path)
assert_valid_knowledge_base(kb)
print(f"Knowledge base valid: {len(kb['experiences'])} experiences, {len(kb['evidence_items'])} evidence items")
