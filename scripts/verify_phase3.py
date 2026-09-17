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
        "canonical_skills", "minimum_years", "source_section", "matched",
    }
    if missing_cols := sorted(expected - req_columns):
        raise SystemExit(f"job_requirements missing columns: {', '.join(missing_cols)}")

    with engine.connect() as conn:
        evidence_count = conn.execute(text("SELECT COUNT(*) FROM evidence_items")).scalar_one()
        skill_count = conn.execute(text("SELECT COUNT(*) FROM skills")).scalar_one()
        policy_count = conn.execute(text("SELECT COUNT(*) FROM targeting_policies")).scalar_one()

    print("Phase 3 schema verified")
    print(f"career evidence available  {evidence_count}")
    print(f"skill taxonomy available   {skill_count}")
    print(f"targeting policies         {policy_count}")


if __name__ == "__main__":
    main()
