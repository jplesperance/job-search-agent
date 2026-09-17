#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from job_agent.db.session import get_session_factory
from job_agent.domain.jobs import TargetingPolicyCreate
from job_agent.domain.models import TargetingPolicy
from job_agent.repositories.sqlalchemy import SqlAlchemyPolicyRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a versioned targeting policy from JSON")
    parser.add_argument("json_file", type=Path)
    args = parser.parse_args()

    payload = TargetingPolicyCreate.model_validate_json(args.json_file.read_text())
    policy = TargetingPolicy(
        name=payload.name,
        version=payload.version,
        active=payload.active,
        target_titles=payload.target_titles,
        target_seniority=payload.target_seniority,
        allowed_locations=payload.allowed_locations,
        remote_allowed=payload.remote_allowed,
        hybrid_allowed=payload.hybrid_allowed,
        onsite_allowed=payload.onsite_allowed,
        minimum_base_salary_usd=payload.minimum_base_salary_usd,
        remote_minimum_base_salary_usd=payload.remote_minimum_base_salary_usd,
        location_compensation_rules=payload.location_compensation_rules,
        required_terms=set(payload.required_terms),
        excluded_terms=set(payload.excluded_terms),
        excluded_title_terms=set(payload.excluded_title_terms),
        exclude_software_engineering_roles=payload.exclude_software_engineering_roles,
        exclude_heavy_coding_roles=payload.exclude_heavy_coding_roles,
        weights=payload.weights,
    )

    with get_session_factory()() as session:
        try:
            stored = SqlAlchemyPolicyRepository(session).add(policy, active=payload.active)
            session.commit()
        except Exception:
            session.rollback()
            raise

    print(json.dumps({
        "id": str(stored.id),
        "name": stored.name,
        "version": stored.version,
        "active": stored.active,
    }, indent=2))


if __name__ == "__main__":
    main()
