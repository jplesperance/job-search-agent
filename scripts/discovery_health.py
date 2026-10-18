"""Inspect discovery health without running a new scan or sending notifications."""
from __future__ import annotations

import argparse
import json
from job_agent.config.settings import get_settings
from job_agent.db.session import get_session_factory
from job_agent.services.discovery_health import source_health_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 4.2 per-source discovery health")
    parser.add_argument("--json", action="store_true", help="Print machine-readable state")
    parser.add_argument("--stale-hours", type=int, default=None)
    args = parser.parse_args()
    hours = args.stale_hours or get_settings().discovery_health_stale_hours
    with get_session_factory()() as session:
        report = source_health_report(session, stale_hours=hours)
    if args.json:
        print(json.dumps(report, indent=2))
        return
    for item in report:
        status = "STALE" if item["stale"] else ("FAIL" if item["incident_open"] else "OK")
        suffix = f" ({item['consecutive_failures']} failed)" if item["incident_open"] else ""
        print(f"{status:5} {item['company']:<25} {item['provider']:<17} {item['last_status']}{suffix}")
        if item["last_error"]:
            print(f"      {item['last_error'][:180]}")
    print(f"Sources: {len(report)} | stale: {sum(bool(x['stale']) for x in report)} | unhealthy: {sum(bool(x['incident_open']) for x in report)}")


if __name__ == "__main__":
    main()
