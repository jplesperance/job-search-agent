from __future__ import annotations

from sqlalchemy import inspect, text

from job_agent.db.session import get_engine


def main() -> None:
    engine = get_engine()
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    required_tables = {
        "discovery_sources",
        "discovery_runs",
        "job_source_postings",
        "notification_states",
    }
    missing = required_tables - tables
    if missing:
        raise SystemExit(f"Missing Phase 4.1 tables: {sorted(missing)}")

    job_columns = {column["name"] for column in inspector.get_columns("job_opportunities")}
    required_columns = {"discovery_source_id", "last_seen_at", "posting_status"}
    missing_columns = required_columns - job_columns
    if missing_columns:
        raise SystemExit(f"Missing discovery job columns: {sorted(missing_columns)}")

    policy_columns = {column["name"] for column in inspector.get_columns("targeting_policies")}
    required_policy_columns = {
        "excluded_title_terms",
        "exclude_software_engineering_roles",
        "exclude_heavy_coding_roles",
    }
    missing_policy_columns = required_policy_columns - policy_columns
    if missing_policy_columns:
        raise SystemExit(f"Missing policy columns: {sorted(missing_policy_columns)}")

    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        source_count = conn.execute(text("SELECT COUNT(*) FROM discovery_sources")).scalar_one()
        run_count = conn.execute(text("SELECT COUNT(*) FROM discovery_runs")).scalar_one()
        posting_count = conn.execute(text("SELECT COUNT(*) FROM job_source_postings")).scalar_one()
        notification_count = conn.execute(text("SELECT COUNT(*) FROM notification_states")).scalar_one()
        active_policy = conn.execute(text(
            "SELECT name, version, exclude_software_engineering_roles, exclude_heavy_coding_roles "
            "FROM targeting_policies WHERE active = true ORDER BY version DESC LIMIT 1"
        )).mappings().first()

    if version != "0008":
        raise SystemExit(f"Expected Alembic 0008, found {version}")
    if active_policy is None:
        raise SystemExit("No active targeting policy found")
    if not active_policy["exclude_software_engineering_roles"]:
        raise SystemExit("Active policy does not exclude software-engineering roles")
    if not active_policy["exclude_heavy_coding_roles"]:
        raise SystemExit("Active policy does not exclude coding-heavy roles")

    print("Phase 4.1 scheduled discovery configuration verified")
    print(f"alembic head              {version}")
    print(f"configured sources        {source_count}")
    print(f"discovery runs            {run_count}")
    print(f"source postings           {posting_count}")
    print(f"notification states       {notification_count}")
    print(f"active policy             {active_policy['name']} v{active_policy['version']}")
    print("software engineering      excluded")
    print("heavy coding              excluded")


if __name__ == "__main__":
    main()
