# Phase 4.2 — Discovery Expansion & Health Monitoring

**Patch version:** `0.4.6`  
**Required base:** working Phase 4.1.1 Pushover release (`0.4.5`; Alembic `0008`)  
**New migration:** `0009`  
**Notification history:** preserved; no rewrite of `notification_states`.  
**Discovery timer:** unchanged; still runs `scripts/run_scheduled_discovery.py`.

## What's included

- **SmartRecruiters public Posting API** source provider (`smartrecruiters`), using paging and full-detail enrichment for security-titled postings. The adapter refuses incomplete pagination, and mandatory detail-fetch failures are reported as partial source scans.
- **Source health tracking:** one row per scanned discovery source recording consecutive failed/partial polls, last success, last error, and an alert incident.
- **Optional Pushover failure and recovery alerts:** one alert per outage after a configurable number of bad scans; one alert on recovery; delivery failures remain retryable. Disabled by default.
- **Empty-board protection:** an established source returning zero postings is marked failed rather than automatically closing all prior jobs. Set `allow_empty_board=true` in that source's `config` if a consistently empty board is expected.
- **Visibility:** `make discovery-health`, `make recent-matches`, `GET /api/v1/discovery/health`.

## Upgrade (stop the timer while upgrading)

```bash
cd ~/job-search-agent
source .venv/bin/activate
sudo systemctl stop job-agent-discovery.timer
# Back up repository and database first (use your normal backup procedure).
unzip -o /path/to/job-agent-phase4.2-discovery-expansion-monitoring-patch-v0.4.6.zip -d .
pip install -e '.[dev]'
PYTHONPATH=src pytest -q
PYTHONPATH=src alembic upgrade head
PYTHONPATH=src alembic current
make verify-phase42
```

Expected: **80 passing tests**, `0009 (head)`, and existing source/notification counts retained. Tests do not require a live ATS or database; `alembic upgrade` and `verify-phase42` validate the live database.

## Try source expansion (ServiceNow)

ServiceNow has a verified SmartRecruiters public careers board, identifier `servicenow`:

```bash
PYTHONPATH=src python scripts/add_discovery_source.py \
  --company ServiceNow --provider smartrecruiters --identifier servicenow
```

The adapter supports other employers with a known `careers.smartrecruiters.com/<companyIdentifier>` careers board; **validate the identifier from the actual employer careers page**, rather than guessing. Nothing is added automatically by installing this patch. Only `smartrecruiters` is new; existing Greenhouse, Lever, Ashby adapters are unchanged.

For a single-provider first poll, use the source UUID printed by `add_discovery_source.py`:

```bash
PYTHONPATH=src python scripts/run_discovery.py --source-id <UUID> --minimum-score 80
```

**Note:** Initial discovery of a newly added source can qualify historic postings. To suppress those older postings before timer notifications resume:

```bash
# This command intentionally runs discovery over all enabled sources first.
PYTHONPATH=src python scripts/run_scheduled_discovery.py --bootstrap-suppress-existing
```

This writes `suppressed` records only where the configured channel has no prior new-match notification. Use it **only if you do not want alerts for jobs already published at the time of onboarding**.

## Enable failure/recovery notifications (optional)

Add to your existing `.env` (keep Pushover credentials unchanged):

```dotenv
DISCOVERY_HEALTH_ALERTS_ENABLED=true
DISCOVERY_HEALTH_FAILURE_THRESHOLD=2
DISCOVERY_HEALTH_STALE_HOURS=12
```

This sends a Pushover push after **2 consecutive** failed/partial polls for a given source and another when it subsequently recovers. Alerts are recorded in `discovery_source_health`, not the job notification table. They are distinct from job-match notifications. Defaults leave health alerts **off** until you opt in.

## Reporting

```bash
make discovery-health
PYTHONPATH=src python scripts/discovery_health.py --json
make recent-matches
PYTHONPATH=src python scripts/recent_matches.py --hours 48 --minimum-score 80
```

`recent-matches` lists currently qualifying canonical jobs **first discovered** during the requested window. It is not a complete history of changes to older postings or scores.

API: `GET /api/v1/discovery/health?stale_hours=12`.

## Reactivate the scheduled timer

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now job-agent-discovery.timer
sudo systemctl list-timers --all | grep job-agent
sudo journalctl -u job-agent-discovery.service -n 80 --no-pager
```

No systemd unit change is needed. The existing service continues running the wrapper and includes health monitoring on subsequent scans. If you need the first health-state update immediately, run:

```bash
PYTHONPATH=src python scripts/run_scheduled_discovery.py
```

## Limits and safety

- **No automatic application submission.** This patch only discovers, analyzes, and notifies.
- Source health alerts identify failures in completed scheduled discovery runs. They **cannot detect a machine-wide outage or a stopped systemd timer**, because the scheduler itself must run to check health. Use an external heartbeat monitor for end-to-end uptime if desired.
- SmartRecruiters listing pages are considered authoritative only after successful, complete pagination. No job closure occurs on a failed/invalid board fetch. If individual mandatory detail requests fail, the source run is marked **partial**; the affected posting is not ingested with a placeholder description.
- SmartRecruiters is a documented public Posting API. A future Workday integration would need separately verified tenant/site configuration; this patch does **not** scrape Workday, LinkedIn, or employer websites.
- Preserve your `.env`; **never include API tokens in logs or source control**.
