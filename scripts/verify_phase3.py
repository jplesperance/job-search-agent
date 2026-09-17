#!/usr/bin/env python3
from sqlalchemy import inspect, text

from job_agent.db.session import get_engine


def main() -> None:
    engine = get_engine()
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    required_tables = {"job_opportunities", "job_requirements", "job_analyses", "targeting_policies"}
    missing = sorted(required_tables - tables)
    if missing:
        raise SystemExit(f"Missing Phase 3 tables: {', '.join(missing)}")

    job_columns = {column["name"] for column in inspector.get_columns("job_opportunities")}
    if "content_hash" not in job_columns:
        raise SystemExit("job_opportunities.content_hash is missing")

    req_columns = {column["name"] for column in inspector.get_columns("job_requirements")}
    expected = {
        "job_id", "ordinal", "requirement_type", "importance", "text",
        "canonical_skills", "minimum_years", "requirement_kind", "skill_match_mode", "source_section", "matched",
    }
    if missing_cols := sorted(expected - req_columns):
        raise SystemExit(f"job_requirements missing columns: {', '.join(missing_cols)}")

    policy_columns = {column["name"] for column in inspector.get_columns("targeting_policies")}
    policy_expected = {"remote_minimum_base_salary_usd", "location_compensation_rules"}
    if missing_cols := sorted(policy_expected - policy_columns):
        raise SystemExit(f"targeting_policies missing Phase 3.1 columns: {', '.join(missing_cols)}")

    analysis_columns = {column["name"] for column in inspector.get_columns("job_analyses")}
    analysis_expected = {"location_context", "confidence_context"}
    if missing_cols := sorted(analysis_expected - analysis_columns):
        raise SystemExit(f"job_analyses missing Phase 3.2 columns: {', '.join(missing_cols)}")

    with engine.connect() as conn:
        evidence_count = conn.execute(text("SELECT COUNT(*) FROM evidence_items")).scalar_one()
        skill_count = conn.execute(text("SELECT COUNT(*) FROM skills")).scalar_one()
        policy_count = conn.execute(text("SELECT COUNT(*) FROM targeting_policies")).scalar_one()
        active = conn.execute(
            text(
                """
                SELECT name, version, remote_minimum_base_salary_usd,
                       jsonb_array_length(location_compensation_rules)
                FROM targeting_policies
                WHERE active = true
                ORDER BY version DESC
                LIMIT 1
                """
            )
        ).one_or_none()

    print("Phase 3.2 schema verified")
    print(f"career evidence available  {evidence_count}")
    print(f"skill taxonomy available   {skill_count}")
    print(f"targeting policies         {policy_count}")
    if active:
        name, version, remote_floor, rule_count = active
        print(f"active policy              {name} v{version}")
        print(f"remote base floor          ${float(remote_floor):,.0f}" if remote_floor else "remote base floor          unset")
        print(f"commute-zone rules         {rule_count}")
    else:
        print("active policy              none (create/activate the v2 policy next)")


if __name__ == "__main__":
    main()
