from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from job_agent.domain.discovery import DiscoveryProvider, DiscoverySourceSummary
from job_agent.services.discovery_adapters import AshbyAdapter, GreenhouseAdapter, LeverAdapter


class FakeHttp:
    def __init__(self, payload):
        self.payload = payload
        self.urls = []

    def get_json(self, url):
        self.urls.append(url)
        return self.payload


def source(provider, identifier="acme"):
    return DiscoverySourceSummary(
        id=uuid4(), company="Acme", provider=provider, board_identifier=identifier,
        enabled=True, priority=100, config={}, created_at=datetime.now(timezone.utc),
    )


def test_greenhouse_normalizes_public_job_board_payload():
    http = FakeHttp({"jobs": [{
        "id": 123,
        "title": "Director of Application Security",
        "location": {"name": "Mountain View, CA"},
        "content": "<h2>Requirements</h2><ul><li>Threat modeling</li></ul>",
        "absolute_url": "https://boards.greenhouse.io/acme/jobs/123",
        "updated_at": "2026-09-16T12:00:00Z",
    }]})
    jobs = GreenhouseAdapter(http).fetch(source(DiscoveryProvider.GREENHOUSE))
    assert len(jobs) == 1
    assert jobs[0].external_id == "123"
    assert jobs[0].location == "Mountain View, CA"
    assert "Threat modeling" in jobs[0].description_raw
    assert "content=true" in http.urls[0]


def test_lever_normalizes_salary_and_plaintext_description():
    http = FakeHttp([{
        "id": "abc",
        "text": "Principal Product Security Engineer",
        "categories": {"location": "Remote", "commitment": "Full-time"},
        "descriptionPlain": "Secure our products.",
        "lists": [{"text": "Requirements", "content": "<li>Application Security</li>"}],
        "additionalPlain": "Equal opportunity employer.",
        "hostedUrl": "https://jobs.lever.co/acme/abc",
        "applyUrl": "https://jobs.lever.co/acme/abc/apply",
        "workplaceType": "remote",
        "salaryRange": {"currency": "USD", "interval": "year", "min": 280000, "max": 340000},
    }])
    jobs = LeverAdapter(http).fetch(source(DiscoveryProvider.LEVER))
    assert len(jobs) == 1
    assert jobs[0].compensation_text == "USD 280,000 - 340,000 per year"
    assert "Application Security" in jobs[0].description_raw
    assert jobs[0].work_arrangement == "remote"


def test_ashby_uses_public_board_and_compensation_summary():
    http = FakeHttp({"jobs": [{
        "title": "Head of AI Security",
        "location": "Palo Alto, CA",
        "isListed": True,
        "workplaceType": "Hybrid",
        "descriptionPlain": "Lead AI/ML security.",
        "publishedAt": "2026-09-16T12:00:00+00:00",
        "employmentType": "FullTime",
        "jobUrl": "https://jobs.ashbyhq.com/acme/uuid",
        "applyUrl": "https://jobs.ashbyhq.com/acme/uuid/application",
        "compensation": {"scrapeableCompensationSalarySummary": "$300K - $360K"},
    }]})
    jobs = AshbyAdapter(http).fetch(source(DiscoveryProvider.ASHBY, "Acme"))
    assert len(jobs) == 1
    assert jobs[0].external_id == "https://jobs.ashbyhq.com/acme/uuid"
    assert jobs[0].compensation_text == "$300K - $360K"
    assert "includeCompensation=true" in http.urls[0]
