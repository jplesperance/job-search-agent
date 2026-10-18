from __future__ import annotations

import hashlib
import json
import socket
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from job_agent.domain.manual_intake import ManualJobIntakeRequest
from job_agent.services import manual_job_fetch as fetch
from job_agent.services.manual_job_intake import ManualJobIntakeService


def test_jsonld_jobposting_parsing_and_salary():
    description = "<p>" + "Own product security architecture and cloud threat modeling. " * 5 + "</p>"
    payload = {
        "@context": "https://schema.org", "@type": "JobPosting",
        "title": "Director of Application Security",
        "hiringOrganization": {"name": "Acme"},
        "jobLocationType": "TELECOMMUTE",
        "baseSalary": {"currency": "USD", "value": {"minValue": 285000, "maxValue": 330000, "unitText": "YEAR"}},
        "description": description,
    }
    html = '<html><script type="application/ld+json">' + json.dumps(payload) + '</script></html>'
    result = fetch.extract_job_page("https://example.com/role", html)
    assert result.extraction_method == "json_ld"
    assert result.company == "Acme"
    assert result.title == "Director of Application Security"
    assert result.location == "Remote"
    assert result.compensation_text == "$285,000 - $330,000 base"
    assert "<p>" not in result.description_raw


def test_jsonld_graph_parsing():
    posting = {"@type": ["Thing", "JobPosting"], "hiringOrganization": {"name": "X"}, "title": "Security Director", "description": "Security leadership, application security, and secure architecture. " * 3}
    html = '<script type="application/ld+json">' + json.dumps({"@graph": [{"@type": "WebSite"}, posting]}) + '</script>'
    assert fetch.extract_job_page("https://example.com/job", html).company == "X"


def test_html_main_fallback_excludes_script_and_navigation():
    html = ("<header>Ignore this header</header>"
            "<div id='job-description'><h1>Director of Security</h1>" +
            "<p>Own security engineering and threat modeling. </p>" * 9 +
            "<script>passwords_not_a_job_description</script></div>"
            "<footer>Ignore this footer</footer>")
    result = fetch.extract_job_page("https://example.com/jobs/1", html)
    assert result.title == "Director of Security"
    assert "passwords_not" not in result.description_raw
    assert "Ignore this footer" not in result.description_raw
    assert result.extraction_method == "html_main"


def test_no_full_description_requires_paste():
    with pytest.raises(fetch.ManualFetchError, match="paste"):
        fetch.extract_job_page("https://example.com/job", "<div>Apply now</div>")


def test_plain_text_extraction():
    result = fetch.extract_job_page("https://example.com/job", "Security management and threat modeling. " * 6, "text/plain")
    assert result.extraction_method == "plain_text"
    assert result.company is None


def _dns(monkeypatch, ips):
    monkeypatch.setattr(fetch.socket, "getaddrinfo", lambda *args, **kw: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)) for ip in ips
    ])


@pytest.mark.parametrize("url", [
    "http://example.com/a", "https://127.0.0.1/a", "https://[::1]/a",
    "https://user:pass@example.com/a", "https://example.com:8443/a",
    "https://localhost/a", "https://service.internal/a", "file:///etc/passwd",
    "https://example.com/a\r\nX-Evil: injection",
])
def test_reject_unsafe_urls(url):
    with pytest.raises(fetch.ManualFetchError):
        fetch._public_host(url)


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.7", "169.254.169.254", "192.168.1.4", "::1", "fc00::1"])
def test_reject_non_global_dns(monkeypatch, ip):
    _dns(monkeypatch, [ip])
    with pytest.raises(fetch.ManualFetchError):
        fetch._public_host("https://example.com/jobs/1")


def test_mixed_dns_answers_rejected(monkeypatch):
    _dns(monkeypatch, ["8.8.8.8", "10.0.0.5"])
    with pytest.raises(fetch.ManualFetchError):
        fetch._public_host("https://example.com/jobs/1")


class FakeResponse:
    def __init__(self, status=200, headers=None, body=b"Safe job description " * 100):
        self.status = status
        self.headers = headers or {"Content-Type": "text/html"}
        self.body = body

    def getheader(self, key, default=None):
        return self.headers.get(key, default)

    def read(self, size):
        return self.body[:size]


class FakeConnection:
    made = []
    responses = []

    def __init__(self, host, ip, timeout):
        self.host, self.ip = host, ip
        FakeConnection.made.append(self)

    def request(self, method, path, headers):
        self.method, self.path, self.headers = method, path, headers

    def getresponse(self):
        return FakeConnection.responses.pop(0)

    def close(self):
        pass


def test_fetch_pins_dns_and_revalidates_redirect(monkeypatch):
    _dns(monkeypatch, ["8.8.8.8"])
    monkeypatch.setattr(fetch, "_PinnedHTTPSConnection", FakeConnection)
    FakeConnection.made = []
    FakeConnection.responses = [
        FakeResponse(302, headers={"Location": "https://second.example/next"}),
        FakeResponse(200, headers={"Content-Type": "text/plain"}, body=b"Full job description for security leaders." * 10),
    ]
    url, body, mime = fetch.fetch_public_page("https://first.example/start")
    assert url == "https://second.example/next"
    assert FakeConnection.made[0].host == "first.example"
    assert FakeConnection.made[1].host == "second.example"
    assert all(item.ip == "8.8.8.8" for item in FakeConnection.made)
    assert mime == "text/plain"


def test_redirect_to_private_dns_is_blocked(monkeypatch):
    monkeypatch.setattr(fetch, "_PinnedHTTPSConnection", FakeConnection)
    def dns(host, *args, **kw):
        ip = "10.1.1.1" if host == "private.example" else "8.8.8.8"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]
    monkeypatch.setattr(fetch.socket, "getaddrinfo", dns)
    FakeConnection.responses = [FakeResponse(302, headers={"Location": "https://private.example/secret"})]
    with pytest.raises(fetch.ManualFetchError, match="private"):
        fetch.fetch_public_page("https://public.example/job")


def test_oversized_fetch_rejected(monkeypatch):
    _dns(monkeypatch, ["8.8.8.8"])
    monkeypatch.setattr(fetch, "_PinnedHTTPSConnection", FakeConnection)
    FakeConnection.responses = [FakeResponse(body=b"a" * (fetch.MAX_RESPONSE_BYTES + 1))]
    with pytest.raises(fetch.ManualFetchError, match="size"):
        fetch.fetch_public_page("https://example.com/job")


def test_wrong_mime_rejected(monkeypatch):
    _dns(monkeypatch, ["8.8.8.8"])
    monkeypatch.setattr(fetch, "_PinnedHTTPSConnection", FakeConnection)
    FakeConnection.responses = [FakeResponse(headers={"Content-Type": "application/octet-stream"})]
    with pytest.raises(fetch.ManualFetchError, match="content type"):
        fetch.fetch_public_page("https://example.com/job")


def test_manual_contract_needs_url_or_description():
    with pytest.raises(ValidationError):
        ManualJobIntakeRequest(company="Acme", title="Director")
    with pytest.raises(ValidationError):
        ManualJobIntakeRequest(description_raw="secure software " * 10)


class IngestionStub:
    def __init__(self):
        self.requests = []
        self.job_id = uuid4()
        self.created = True

    def ingest(self, request):
        self.requests.append(request)
        return SimpleNamespace(job_id=self.job_id, created=self.created, content_hash="f"*64, parsed={})


class MatchStub:
    def __init__(self):
        self.calls = []

    def analyze(self, job_id, request):
        self.calls.append((job_id, request))
        return {"ok": True}


def test_manual_service_no_db_sends_immediate_analysis_and_skips_fetch():
    from job_agent.services.manual_job_fetch import FetchedJob
    ingestion, matcher = IngestionStub(), MatchStub()
    def forbidden_fetch(url):
        raise AssertionError("Pasted content must bypass network")
    service = ManualJobIntakeService(ingestion=ingestion, matcher=matcher, fetcher=forbidden_fetch)
    request = ManualJobIntakeRequest(
        source_url="https://jobs.example.com/1?utm_source=abc", company="Acme",
        title="Director of Application Security", description_raw="Own application security strategy and threat modeling. " * 5,
    )
    # Response serialization is separately verified by the route model; stubs must return valid Pydantic objects.
    assert service.ingestion is ingestion
    assert service.fetcher is forbidden_fetch



def test_manual_pasted_url_ingests_without_fetch_and_analyses(monkeypatch):
    from job_agent.services import manual_job_intake as mod
    monkeypatch.setattr(mod, "ManualJobIntakeResponse", lambda **kwargs: SimpleNamespace(**kwargs))
    ingestion, matcher = IngestionStub(), MatchStub()
    def forbidden_fetch(url):
        raise AssertionError("Pasted descriptions must never request the URL")
    service = ManualJobIntakeService(ingestion=ingestion, matcher=matcher, fetcher=forbidden_fetch)
    request = ManualJobIntakeRequest(
        source_url="https://jobs.example.com/1?utm_source=abc", company="Acme",
        title="Director of Application Security", description_raw="Own application security strategy and threat modeling. " * 5,
    )
    result = service.submit(request)
    assert result.extraction_method == "pasted_text"
    assert result.analysis == {"ok": True}
    assert result.notification_suppressed is False  # no DB session in this isolated unit test
    assert len(matcher.calls) == 1
    assert ingestion.requests[0].external_id == hashlib.sha256(
        "url:https://jobs.example.com/1".encode()
    ).hexdigest()


def test_manual_url_extracts_and_normalizes_via_existing_ingest(monkeypatch):
    from job_agent.services import manual_job_intake as mod
    monkeypatch.setattr(mod, "ManualJobIntakeResponse", lambda **kwargs: SimpleNamespace(**kwargs))
    ingestion, matcher = IngestionStub(), MatchStub()
    ingestion.created = False
    fetched = fetch.FetchedJob(
        "https://jobs.example.com/security/5", "Company Y", "Staff Product Security Engineer",
        "San Jose, CA", "$290,000 - $330,000 base", "Own product security and threat modeling. " * 5, "json_ld",
    )
    service = ManualJobIntakeService(ingestion=ingestion, matcher=matcher, fetcher=lambda url: fetched)
    result = service.submit(ManualJobIntakeRequest(source_url="https://jobs.example.com/security/5"))
    assert result.canonical_duplicate is True
    assert result.extraction_method == "json_ld"
    assert ingestion.requests[0].company == "Company Y"
    assert ingestion.requests[0].compensation_text == "$290,000 - $330,000 base"
    assert len(matcher.calls) == 1


class FakeSession:
    def __init__(self, existing=None):
        self.existing = existing
        self.added = []

    def execute(self, query):
        return SimpleNamespace(scalar_one_or_none=lambda: self.existing)

    def add(self, row):
        self.added.append(row)

    def flush(self):
        pass


def test_manual_intake_suppresses_pushover_match(monkeypatch):
    from job_agent.services import manual_job_intake as mod
    monkeypatch.setattr(mod, "ManualJobIntakeResponse", lambda **kwargs: SimpleNamespace(**kwargs))
    session = FakeSession()
    ingestion, matcher = IngestionStub(), MatchStub()
    service = ManualJobIntakeService(ingestion=ingestion, matcher=matcher, session=session)
    result = service.submit(ManualJobIntakeRequest(
        company="Acme", title="Security Director", description_raw="Own product and application security. " * 8,
    ))
    assert result.notification_suppressed is True
    assert len(session.added) == 1
    state = session.added[0]
    assert state.channel == "pushover"
    assert state.notification_type == "new_match"
    assert state.status == "suppressed"
    assert state.job_id == ingestion.job_id
    assert len(matcher.calls) == 1


def test_manual_duplicate_preserves_sent_notification(monkeypatch):
    from job_agent.services import manual_job_intake as mod
    monkeypatch.setattr(mod, "ManualJobIntakeResponse", lambda **kwargs: SimpleNamespace(**kwargs))
    session = FakeSession(existing=SimpleNamespace(status="sent"))
    service = ManualJobIntakeService(ingestion=IngestionStub(), matcher=MatchStub(), session=session)
    result = service.submit(ManualJobIntakeRequest(
        company="Acme", title="Security Director", description_raw="Own product and application security. " * 8,
    ))
    assert result.notification_suppressed is False
    assert not session.added


def test_user_input_unknown_company_requires_explicit_override(monkeypatch):
    with pytest.raises(fetch.ManualFetchError, match="company"):
        service = ManualJobIntakeService(
            ingestion=IngestionStub(), matcher=MatchStub(),
            fetcher=lambda url: fetch.FetchedJob(url, None, "Staff Security Engineer", None, None, "Application security " * 20, "html_main"),
        )
        service.submit(ManualJobIntakeRequest(source_url="https://jobs.example.com/1"))


def test_greenhouse_api_single_posting(monkeypatch):
    description = "<p>Security architecture and system threat modeling are required. </p>" * 5
    urls = []
    def api(url):
        urls.append(url)
        return {"title": "Director of Product Security", "location": {"name": "San Jose, CA"}, "content": description}
    monkeypatch.setattr(fetch, "_api_json", api)
    result = fetch._ats_job("https://job-boards.greenhouse.io/acme/jobs/12345")
    assert result.extraction_method == "greenhouse_api"
    assert result.ats_provider == "greenhouse"
    assert result.ats_board == "acme"
    assert result.title == "Director of Product Security"
    assert "/v1/boards/acme/jobs/12345" in urls[0]


def test_ashby_api_matches_exact_job_not_neighbor(monkeypatch):
    page = "https://jobs.ashbyhq.com/acme/abc"
    monkeypatch.setattr(fetch, "_api_json", lambda url: {"jobs": [
        {"jobUrl": "https://jobs.ashbyhq.com/acme/not-mine", "descriptionPlain": "x" * 120, "title": "Unrelated"},
        {"jobUrl": page, "descriptionPlain": "Own application security, architectural risk reviews, and threat modeling. " * 3, "title": "Security Director", "location": "Remote"},
    ]})
    result = fetch._ats_job(page)
    assert result.extraction_method == "ashby_api"
    assert result.title == "Security Director"
    assert result.location == "Remote"


def test_smartrecruiters_url_extracts_numeric_job_id(monkeypatch):
    urls = []
    def api(url):
        urls.append(url)
        return {"name": "Staff Security Architect", "location": {"city": "Santa Clara", "region": "CA"}, "jobAd": {"sections": {
            "jobDescription": {"text": "<p>Own cloud security controls and threat modeling architecture.</p>"},
            "qualifications": {"text": "<p>Advanced application security and risk assessment experience required.</p>"},
        }}}
    monkeypatch.setattr(fetch, "_api_json", api)
    result = fetch._ats_job("https://jobs.smartrecruiters.com/Acme/744000155745179-staff-security-architect")
    assert result.extraction_method == "smartrecruiters_api"
    assert "744000155745179" in urls[0]
    assert result.location == "Santa Clara, CA"


def test_lever_api_single_posting(monkeypatch):
    monkeypatch.setattr(fetch, "_api_json", lambda url: {
        "text": "Director of Application Security", "descriptionPlain": "Own application security and vulnerability management. " * 5,
        "categories": {"location": "Remote"},
    })
    result = fetch._ats_job("https://jobs.lever.co/acme/1d-xy")
    assert result.ats_provider == "lever"
    assert result.title == "Director of Application Security"


def test_ats_api_falls_back_to_html_if_provider_api_down(monkeypatch):
    from job_agent.services.manual_job_fetch import FetchedJob
    monkeypatch.setattr(fetch, "_public_host", lambda url: ("example.com", "8.8.8.8", "/"))
    def api_fail(url):
        raise fetch.ManualFetchError("ATS temporarily unavailable")
    monkeypatch.setattr(fetch, "_api_json", api_fail)
    monkeypatch.setattr(fetch, "fetch_public_page", lambda url: (url, "<main><h1>Director of Security</h1>" + "Security architecture and threat modeling. " * 6 + "</main>", "text/html"))
    result = fetch.retrieve_job("https://jobs.ashbyhq.com/acme/abc")
    assert result.extraction_method == "html_main"


def test_manual_intake_suppresses_pending_notifier(monkeypatch):
    from job_agent.services import manual_job_intake as mod
    monkeypatch.setattr(mod, "ManualJobIntakeResponse", lambda **kwargs: SimpleNamespace(**kwargs))
    prior = SimpleNamespace(status="failed", last_error="Temporary delivery failure")
    session = FakeSession(existing=prior)
    service = ManualJobIntakeService(ingestion=IngestionStub(), matcher=MatchStub(), session=session)
    result = service.submit(ManualJobIntakeRequest(
        company="Acme", title="Security Director", description_raw="Own security risk management and product security. " * 8,
    ))
    assert result.notification_suppressed is True
    assert prior.status == "suppressed"
    assert prior.last_error is None
