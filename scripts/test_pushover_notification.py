"""Send one direct Pushover test without creating a notification_states row."""
from __future__ import annotations

import argparse

from job_agent.config.settings import get_settings
from job_agent.services.notifications import PushoverNotifier, build_notifier


def main() -> None:
    parser = argparse.ArgumentParser(description="Send one test Pushover push notification")
    parser.add_argument("--message", default="Job Search Agent: Pushover integration test")
    parser.add_argument("--title", default="Job Agent Test")
    parser.add_argument("--url", default="https://pushover.net/")
    args = parser.parse_args()

    notifier = build_notifier(get_settings())
    if not isinstance(notifier, PushoverNotifier):
        raise SystemExit(
            "Set NOTIFICATION_PROVIDER=pushover and provide PUSHOVER_API_TOKEN "
            "and PUSHOVER_USER_KEY in .env first."
        )

    # Deliberately bypass NotificationService: no job_id and no deduplication state.
    request_id = notifier.send(args.message, title=args.title, url=args.url)
    print(f"Pushover API accepted test notification; request_id={request_id or 'not provided'}")
    print("This test did not read or modify notification_states.")


if __name__ == "__main__":
    main()
