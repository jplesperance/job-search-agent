# Phase 4.1 Design

## Canonical job identity

`job_opportunities` remains the canonical opening. `job_source_postings` records every provider-specific
representation of that opening. Notification idempotency is attached to the canonical job, not the provider posting.

Automatic merge confidence order:

1. same source + external ID;
2. same normalized source/application URL;
3. exact company + title + description content hash;
4. cross-source normalized company + title + location with >= 0.97 normalized description similarity.

Ambiguous candidates remain separate.

## Notification state

Statuses: `pending`, `sent`, `failed`, `suppressed`.

The database unique constraint `(job_id, channel, notification_type)` prevents duplicate new-match delivery.
Failures remain retryable up to the configured attempt limit.

## Scheduler

The Python layer does not run a resident scheduler. A systemd timer starts a oneshot process every four hours.
The oneshot process performs discovery, commits it, then evaluates current surfaced candidates and delivers
notifications whose canonical job lacks a terminal notification state.
