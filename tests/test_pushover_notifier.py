from __future__ import annotations

import httpx
import pytest

from job_agent.config.settings import Settings
from job_agent.services.notifications import (
    ConsoleNotifier,
    PushoverNotifier,
    build_notifier,
)


def test_build_notifier_disabled_and_console_modes():
    assert build_notifier(Settings(_env_file=None, notification_provider="disabled")) is None
    assert isinstance(
        build_notifier(Settings(_env_file=None, notification_provider="console")),
        ConsoleNotifier,
    )


def test_build_pushover_rejects_missing_credentials():
    with pytest.raises(RuntimeError, match="PUSHOVER_API_TOKEN, PUSHOVER_USER_KEY"):
        build_notifier(Settings(_env_file=None, notification_provider="pushover"))


def test_build_pushover_uses_configured_keys_and_device():
    notifier = build_notifier(
        Settings(
            _env_file=None,
            notification_provider="pushover",
            pushover_api_token="token-example",
            pushover_user_key="user-example",
            pushover_device="my-iphone",
        )
    )
    assert isinstance(notifier, PushoverNotifier)
    assert notifier.channel == "pushover"
    assert notifier.device == "my-iphone"


def test_pushover_sends_clickable_job_url_and_returns_request_id(monkeypatch):
    seen = {}

    def fake_post(url, *, data, timeout):
        seen.update(url=url, data=data, timeout=timeout)
        return httpx.Response(200, request=httpx.Request("POST", url), json={"status": 1, "request": "req-123"})

    monkeypatch.setattr("job_agent.services.notifications.httpx.post", fake_post)
    notifier = PushoverNotifier(api_token="test-token", user_key="test-user")
    request_id = notifier.send(
        "Acme — Director of Security\nScore: 91.0",
        title="New Job Match",
        url="https://jobs.example.com/acme/123",
    )
    assert request_id == "req-123"
    assert seen["url"] == "https://api.pushover.net/1/messages.json"
    assert seen["data"] == {
        "token": "test-token",
        "user": "test-user",
        "message": "Acme — Director of Security\nScore: 91.0",
        "title": "New Job Match",
        "url": "https://jobs.example.com/acme/123",
        "url_title": "Open job posting",
    }
    assert seen["timeout"] == 20.0


def test_pushover_rejects_non_success_json_even_with_http_200(monkeypatch):
    monkeypatch.setattr(
        "job_agent.services.notifications.httpx.post",
        lambda *args, **kwargs: httpx.Response(
            200,
            request=httpx.Request("POST", "https://api.pushover.net/1/messages.json"),
            json={"status": 0, "errors": ["invalid user"]}
        ),
    )
    notifier = PushoverNotifier(api_token="test-token", user_key="test-user")
    with pytest.raises(RuntimeError, match="invalid user"):
        notifier.send("Hello")


def test_pushover_http_error_raises_for_notification_retries(monkeypatch):
    monkeypatch.setattr(
        "job_agent.services.notifications.httpx.post",
        lambda *args, **kwargs: httpx.Response(
            429, request=httpx.Request("POST", "https://api.pushover.net/1/messages.json")
        ),
    )
    notifier = PushoverNotifier(api_token="test-token", user_key="test-user")
    with pytest.raises(httpx.HTTPStatusError):
        notifier.send("Hello")


def test_console_mode_keeps_full_job_link(capsys):
    ConsoleNotifier().send("Score 92.0", title="New Job Match", url="https://example.com/job")
    output = capsys.readouterr().out
    assert "Score 92.0" in output
    assert "https://example.com/job" in output


def test_pushover_omits_invalid_or_overlong_supplementary_url(monkeypatch):
    captured = {}

    def fake_post(url, *, data, timeout):
        captured.update(data)
        return httpx.Response(200, request=httpx.Request("POST", url), json={"status": 1, "request": "req-456"})

    monkeypatch.setattr("job_agent.services.notifications.httpx.post", fake_post)
    PushoverNotifier(api_token="test-token", user_key="test-user").send(
        "Hello", url="https://example.com/" + "x" * 600
    )
    assert "url" not in captured


def test_pushover_rejects_oversize_message_without_calling_api(monkeypatch):
    def unexpected_post(*args, **kwargs):
        raise AssertionError("must not send")
    monkeypatch.setattr("job_agent.services.notifications.httpx.post", unexpected_post)
    with pytest.raises(ValueError, match="1024"):
        PushoverNotifier(api_token="t", user_key="u").send("x" * 1025)


def test_old_twilio_env_does_not_break_settings_but_provider_is_retired():
    settings = Settings(
        _env_file=None,
        notification_provider="twilio",
        twilio_account_sid="legacy",
        twilio_auth_token="legacy",
        twilio_from_number="legacy",
    )
    with pytest.raises(RuntimeError, match="Unsupported notification provider"):
        build_notifier(settings)


def test_notification_service_persists_pushover_request_id_and_deduplicates():
    from datetime import datetime, timezone
    from uuid import uuid4
    from job_agent.domain.discovery import DiscoveryCandidateSummary
    from job_agent.services.notifications import NotificationService, NotificationStatus

    class FakeResult:
        def __init__(self, row):
            self.row = row

        def scalar_one_or_none(self):
            return self.row

    class FakeSession:
        def __init__(self):
            self.row = None

        def execute(self, stmt):
            return FakeResult(self.row)

        def add(self, row):
            self.row = row

        def flush(self):
            pass

    class FakePushover:
        channel = "pushover"

        def __init__(self):
            self.calls = []

        def send(self, message, *, title=None, url=None):
            self.calls.append((message, title, url))
            return "pushover-request-001"

    candidate = DiscoveryCandidateSummary(
        job_id=uuid4(),
        company="Example",
        title="Director of Application Security",
        location="San Jose, CA",
        compensation_text="$300,000 base",
        source_url="https://jobs.example.org/director",
        provider_source="greenhouse:example",
        posting_status="open",
        total_score=94.2,
        hard_filter_passed=True,
        analyzed_at=datetime.now(timezone.utc),
    )
    session = FakeSession()
    notifier = FakePushover()
    service = NotificationService(session, notifier)
    first = service.notify(candidate)
    second = service.notify(candidate)

    assert first.status is NotificationStatus.SENT
    assert first.attempted is True
    assert first.provider_message_id == "pushover-request-001"
    assert session.row.provider_message_id == "pushover-request-001"
    assert session.row.channel == "pushover"
    assert session.row.attempt_count == 1
    assert second.status is NotificationStatus.SENT
    assert second.attempted is False
    assert len(notifier.calls) == 1
    message, title, url = notifier.calls[0]
    assert "Example" in message and "94.2" in message
    assert url == candidate.source_url
    assert url not in message  # API supplementary link, not duplicated in body
    assert title == "New Job Match"
