# Phase 4.2 architecture and operational notes

## Discovery sources

New `DiscoveryProvider.SMARTRECRUITERS` consumes SmartRecruiters' documented, public Posting API via:

- `GET /v1/companies/{companyIdentifier}/postings?limit=100&offset=N`
- `GET /v1/companies/{companyIdentifier}/postings/{postingId}`

Details are fetched only after title-based prefiltering. This minimizes provider requests but still feeds the full description back through `evaluate_role_preferences`, so coding-heavy exclusions remain effective. An invalid/truncated listing page raises `DiscoveryFetchError`; no empty/partial page can silently close existing postings. `enrich_mandatory=True` means a failed detail fetch marks a scan partial, rather than ingesting an empty placeholder.

Official reference: https://developers.smartrecruiters.com/docs/endpoints

## Health state machine

Authoritative data remains `discovery_runs`. `discovery_source_health` is a persisted operational projection, updated once per source per scheduled run. It is *not* the source of job-match truth.

- `COMPLETED`: reset failure streak; remember last successful poll; enqueue recovery alert only if a failure alert had previously been sent.
- `PARTIAL` or `FAILED`: increment streak and preserve last error; open an incident if needed.
- Streak >= `DISCOVERY_HEALTH_FAILURE_THRESHOLD`: send one alert if alerts are enabled. Persist `failure_alert_sent` on successful delivery. Retry if Pushover fails.
- Recovery: if an incident was previously alerted, send one recovery push and clear pending state.

The health table has a primary key equal to `discovery_sources.id`. It doesn't modify or delete historical `discovery_runs`, `job_source_postings`, or `notification_states` records.

## Operational reporting

`discovery_health.py` reports incident/staleness state and supports machine-readable JSON; the API endpoint returns the same projection. A source is considered stale if it is enabled and its most recent known check exceeds `DISCOVERY_HEALTH_STALE_HOURS` (default 12h).

`recent_matches.py` displays currently eligible jobs first discovered within a time window, all canonical source-posting references, and job-match Pushover delivery status.

## Schedule semantics

Phase 4.1's systemd one-shot timer remains the scheduler. Discovery data is committed before health-alert delivery, and health-state commits occur before ordinary job-match notification delivery. A failed Pushover push cannot reverse a completed ATS discovery transaction. A process outage before health processing is visible in systemd/journal logs but does not self-notify.
