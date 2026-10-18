# Phase 4.1.1 — Pushover Notification Transport

This is a **flat, root-relative overlay** on Phase 4.1 (`job-agent-system` v0.4.4,
Alembic 0008). It replaces the Twilio sending implementation with Pushover,
while preserving console notifications, deduplication, retry state, and the
existing systemd scheduled-discovery units.

## Changed files

- `src/job_agent/services/notifications.py` — PushoverNotifier, click-through
  job posting URL, provider request ID persistence, and console compatibility.
- `src/job_agent/config/settings.py` — Pushover credentials and optional device.
  Legacy Twilio settings are *accepted but ignored* to avoid breaking existing
  `.env` files that were populated before upgrading.
- `scripts/test_pushover_notification.py` — standalone, real push test without
  inserting a `notification_states` row.
- `.env.example` — Pushover configuration instead of Twilio.
- `tests/test_pushover_notifier.py` — mocked delivery tests (no external sends).
- `pyproject.toml` — version `0.4.5`.

**Database migration:** none. Schema remains at Alembic `0008`.

## Install

If a systemd discovery timer is already running, stop it before switching the
provider and baselining existing matches:

```bash
sudo systemctl stop job-agent-discovery.timer
```

Then apply the overlay:

```bash
cd ~/job-search-agent
source .venv/bin/activate
unzip -o /path/to/job-agent-phase4.1.1-pushover-patch-v0.4.5.zip -d .
pip install -e '.[dev]'
PYTHONPATH=src pytest -q
PYTHONPATH=src alembic current  # expected 0008 (head)
make verify-phase4
```

## Pushover setup

1. Install Pushover on your iPhone or Android device and create/log in to your
   Pushover account at https://pushover.net/ . Find your **user key** there.
2. Create an application at https://pushover.net/apps/build and copy its
   **application API token**.
3. Set the following values in the repository's `.env` (never commit it):

```dotenv
NOTIFICATION_PROVIDER=pushover
PUSHOVER_API_TOKEN=your_app_token
PUSHOVER_USER_KEY=your_user_key
# Optional: restrict notifications to a specific named device
PUSHOVER_DEVICE=
NOTIFICATION_MAX_ATTEMPTS=3
SCHEDULED_DISCOVERY_MINIMUM_SCORE=80
```

**Do not add `NOTIFICATION_RECIPIENT` for Pushover.** The app token and user key
are sufficient; `NOTIFICATION_RECIPIENT` is a legacy SMS setting.

## Send ONE push without touching job notification state

```bash
PYTHONPATH=src python scripts/test_pushover_notification.py
```

This deliberately bypasses scheduled discovery and `notification_states`. The
Pushover API `request` ID is printed if accepted. It is not a delivery receipt.

## Baseline existing matches for the new notification channel

Deduplication keys are `(canonical_job_id, channel, notification_type)`. If you
previously established the baseline using the `console` channel, those rows
**do not suppress** the newly configured `pushover` channel.

To avoid receiving old matches, run this once before enabling scheduled sends:

```bash
PYTHONPATH=src python scripts/run_scheduled_discovery.py --bootstrap-suppress-existing
```

The command performs discovery, then records current qualifying matches with
`status=suppressed` for channel `pushover`; it will **not** send notifications.

Then verify recurring execution (one run per schedule):

```bash
PYTHONPATH=src python scripts/run_scheduled_discovery.py
PYTHONPATH=src python scripts/run_scheduled_discovery.py
```

No already-suppressed canonical jobs should be notified on either subsequent run.
New qualifying matches will receive one Pushover push containing title, match
score, location and compensation summary, plus a clickable job URL when available.

## Scheduling

Existing systemd `job-agent-discovery.service` and `.timer` units need no change.
After successful test delivery and baselining, start the timer again if it
was previously installed and enabled:

```bash
sudo systemctl start job-agent-discovery.timer
systemctl list-timers job-agent-discovery.timer
journalctl -u job-agent-discovery.service -n 100 --no-pager
```

## Notes

- This package does not alter or reset notification history. Existing
  `console`/`sms` rows remain for audit, but Pushover has an independent channel.
- Do not manually delete notification rows to force an alert; the direct test
  script is safer.
- Pushover `status=1` means the API accepted and queued the notification,
  not that a device displayed it.
- This phase still relies on the existing synchronous notification outbox;
  if a process exits after Pushover accepts a push but before the DB commit,
  a duplicate may be retried. This patch does not claim exactly-once delivery.
