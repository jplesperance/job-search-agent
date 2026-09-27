# Phase 4.1 — Scheduled Discovery, Cross-Source Canonicalization, and Notifications

Phase 4.1 is a root-relative overlay for a verified Phase 4.0.3 + 4.0.3.1 installation.
The package version is `0.4.4`; the feature milestone is Phase 4.1.

## What changes

- Adds `job_source_postings`, which maps provider-specific postings to canonical jobs.
- Adds conservative cross-source deduplication using, in order:
  1. provider source + external posting ID;
  2. normalized posting/application URL;
  3. existing exact company/title/content fingerprint;
  4. normalized company/title/location plus >= 0.97 description similarity across different sources.
- Tracks open/closed status per source posting. A canonical job closes only after all known source postings close.
- Adds `notification_states` with unique `(job_id, channel, notification_type)` idempotency.
- Adds console and Twilio SMS notifiers.
- Adds `scripts/run_scheduled_discovery.py`.
- Adds sample systemd oneshot service + four-hour timer.

## Install

From the repository root:

```bash
unzip -o /path/to/job-agent-phase4.1-scheduled-notifications-patch-v0.4.4.zip -d .
source .venv/bin/activate
pip install -e '.[dev]'
PYTHONPATH=src pytest -q
PYTHONPATH=src alembic upgrade head
make verify-phase41
```

Expected Alembic head:

```text
0008
```

## Configure notifications

Start safely with console delivery:

```dotenv
SCHEDULED_DISCOVERY_MINIMUM_SCORE=80
NOTIFICATION_PROVIDER=console
NOTIFICATION_MAX_ATTEMPTS=3
```

Run once:

```bash
make run-scheduled-discovery
```

The first notification-enabled run will notify for every currently open qualifying canonical job
that has no notification-state row yet. If you want to establish the current jobs as a baseline
without sending them, run once with:

```bash
PYTHONPATH=src python scripts/run_scheduled_discovery.py --bootstrap-suppress-existing
```

After that, normal scheduled runs notify only newly qualifying canonical jobs.

For Twilio SMS:

```dotenv
NOTIFICATION_PROVIDER=twilio
NOTIFICATION_RECIPIENT=+1XXXXXXXXXX
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM_NUMBER=+1XXXXXXXXXX
```

Secrets belong only in `.env`; do not commit them.

## Schedule with systemd

Review `deploy/systemd/job-agent-discovery.service` first. It assumes:

- Linux user: `jese`
- repository: `/home/jese/job-search-agent`
- virtualenv: `/home/jese/job-search-agent/.venv`

Install:

```bash
sudo cp deploy/systemd/job-agent-discovery.service /etc/systemd/system/
sudo cp deploy/systemd/job-agent-discovery.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now job-agent-discovery.timer
systemctl list-timers job-agent-discovery.timer
```

Inspect runs:

```bash
journalctl -u job-agent-discovery.service -n 100
```

## Important operational properties

- Discovery is committed before notifications are attempted.
- A failed SMS cannot roll back discovery.
- Failed delivery is retried until `NOTIFICATION_MAX_ATTEMPTS` is reached.
- Sent/suppressed notifications are never resent for the same canonical job/channel/type.
- Migration `0008` does **not** destructively merge historical duplicate canonical jobs. It only
  establishes source mappings. Future discovery gains cross-source deduplication immediately.
