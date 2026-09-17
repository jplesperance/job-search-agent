from __future__ import annotations

from sqlalchemy import inspect, text

from job_agent.db.session import get_engine


def main() -> None:
    engine = get_engine()
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    required_tables = {"discovery_sources", "discovery_runs"}
    missing = required_tables - tables
    if missing:
        raise SystemExit(f"Missing Phase 4 tables: {sorted(missing)}")

    job_columns = {column["name"] for column in inspector.get_columns("job_opportunities")}
    required_columns = {"discovery_source_id", "last_seen_at", "posting_status"}
    missing_columns = required_columns - job_columns
    if missing_columns:
        raise SystemExit(f"Missing Phase 4 job columns: {sorted(missing_columns)}")

    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        source_count = conn.execute(text("SELECT COUNT(*) FROM discovery_sources")).scalar_one()
        run_count = conn.execute(text("SELECT COUNT(*) FROM discovery_runs")).scalar_one()
    policy_columns = {column["name"] for column in inspector.get_columns("targeting_policies")}
    required_policy_columns = {
        "excluded_title_terms",
        "exclude_software_engineering_roles",
        "exclude_heavy_coding_roles",
    }
    missing_policy_columns = required_policy_columns - policy_columns
    if missing_policy_columns:
        raise SystemExit(f"Missing Phase 4.0.1 policy columns: {sorted(missing_policy_columns)}")

    if version != "0007":
        raise SystemExit(f"Expected Alembic 0007, found {version}")

    print("Phase 4.0.1 discovery schema verified")
    print(f"alembic head              {version}")
    print(f"configured sources        {source_count}")
    print(f"discovery runs            {run_count}")


if __name__ == "__main__":
    main()
