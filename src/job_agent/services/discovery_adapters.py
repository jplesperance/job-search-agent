from __future__ import annotations

import html
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote

import httpx

from job_agent.domain.discovery import DiscoveryPosting, DiscoveryProvider, DiscoverySourceSummary


class DiscoveryFetchError(RuntimeError):
    pass


class _HTMLTextExtractor(HTMLParser):
    BLOCK_TAGS = {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "h5", "h6", "section"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() == "li":
            self.parts.append("\n- ")
        elif tag.lower() in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        value = html.unescape("".join(self.parts))
        value = re.sub(r"[ \t]+", " ", value)
        value = re.sub(r"\n[ \t]+", "\n", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value.strip()


def html_to_text(value: str | None) -> str:
    if not value:
        return ""
    parser = _HTMLTextExtractor()
    parser.feed(value)
    parser.close()
    return parser.text()


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class JsonHttpClient:
    def __init__(self, *, timeout: float = 20.0, attempts: int = 3) -> None:
        self.timeout = timeout
        self.attempts = attempts

    def get_json(self, url: str) -> Any:
        last_error: Exception | None = None
        headers = {
            "Accept": "application/json",
            "User-Agent": "job-agent-discovery/0.4 (+personal job-search automation)",
        }
        for attempt in range(self.attempts):
            try:
                with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
                    response = client.get(url)
                if response.status_code == 429 or response.status_code >= 500:
                    raise DiscoveryFetchError(f"HTTP {response.status_code} from {url}")
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError, DiscoveryFetchError) as exc:
                last_error = exc
                if attempt + 1 < self.attempts:
                    time.sleep(0.25 * (2**attempt))
        raise DiscoveryFetchError(f"Unable to fetch {url}: {last_error}") from last_error


class DiscoveryAdapter(ABC):
    provider: DiscoveryProvider

    def __init__(self, http: JsonHttpClient | None = None) -> None:
        self.http = http or JsonHttpClient()

    @abstractmethod
    def fetch(self, source: DiscoverySourceSummary) -> list[DiscoveryPosting]:
        raise NotImplementedError


class GreenhouseAdapter(DiscoveryAdapter):
    provider = DiscoveryProvider.GREENHOUSE

    def fetch(self, source: DiscoverySourceSummary) -> list[DiscoveryPosting]:
        token = quote(source.board_identifier.strip(), safe="")
        url = f"https://api.greenhouse.io/v1/boards/{token}/jobs?content=true"
        payload = self.http.get_json(url)
        jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
        results: list[DiscoveryPosting] = []
        for job in jobs:
            if not isinstance(job, dict):
                continue
            external_id = str(job.get("id") or "").strip()
            title = str(job.get("title") or "").strip()
            description = html_to_text(job.get("content"))
            if not external_id or not title or not description:
                continue
            location_obj = job.get("location") or {}
            location = location_obj.get("name") if isinstance(location_obj, dict) else None
            results.append(
                DiscoveryPosting(
                    provider=self.provider,
                    external_id=external_id,
                    company=source.company,
                    title=title,
                    location=str(location).strip() if location else None,
                    compensation_text=None,
                    description_raw=description,
                    source_url=job.get("absolute_url"),
                    published_at=_parse_dt(job.get("updated_at")),
                )
            )
        return results


class LeverAdapter(DiscoveryAdapter):
    provider = DiscoveryProvider.LEVER

    def fetch(self, source: DiscoverySourceSummary) -> list[DiscoveryPosting]:
        site = quote(source.board_identifier.strip(), safe="")
        region = str(source.config.get("region", "global")).lower()
        host = "api.eu.lever.co" if region == "eu" else "api.lever.co"
        url = f"https://{host}/v0/postings/{site}?mode=json"
        payload = self.http.get_json(url)
        jobs = payload if isinstance(payload, list) else []
        results: list[DiscoveryPosting] = []
        for job in jobs:
            if not isinstance(job, dict):
                continue
            external_id = str(job.get("id") or "").strip()
            title = str(job.get("text") or "").strip()
            categories = job.get("categories") or {}
            location = categories.get("location") if isinstance(categories, dict) else None
            description = str(job.get("descriptionPlain") or "").strip()
            if job.get("lists"):
                list_parts: list[str] = []
                for item in job.get("lists") or []:
                    if not isinstance(item, dict):
                        continue
                    heading = str(item.get("text") or "").strip()
                    content = html_to_text(item.get("content"))
                    if heading or content:
                        list_parts.append(f"{heading}\n{content}".strip())
                if list_parts:
                    description = f"{description}\n\n" + "\n\n".join(list_parts)
            additional = str(job.get("additionalPlain") or "").strip()
            if additional:
                description = f"{description}\n\n{additional}".strip()
            if not external_id or not title or not description:
                continue

            salary = job.get("salaryRange")
            compensation_text = None
            if isinstance(salary, dict) and salary.get("min") is not None and salary.get("max") is not None:
                currency = str(salary.get("currency") or "USD").upper()
                interval = str(salary.get("interval") or "year")
                compensation_text = (
                    f"{currency} {float(salary['min']):,.0f} - {float(salary['max']):,.0f} per {interval}"
                )
            elif job.get("salaryDescriptionPlain"):
                compensation_text = str(job.get("salaryDescriptionPlain")).strip()

            results.append(
                DiscoveryPosting(
                    provider=self.provider,
                    external_id=external_id,
                    company=source.company,
                    title=title,
                    location=str(location).strip() if location else None,
                    work_arrangement=str(job.get("workplaceType") or "").strip() or None,
                    compensation_text=compensation_text,
                    description_raw=description,
                    source_url=job.get("hostedUrl"),
                    apply_url=job.get("applyUrl"),
                    employment_type=(categories.get("commitment") if isinstance(categories, dict) else None),
                )
            )
        return results


class AshbyAdapter(DiscoveryAdapter):
    provider = DiscoveryProvider.ASHBY

    def fetch(self, source: DiscoverySourceSummary) -> list[DiscoveryPosting]:
        board = quote(source.board_identifier.strip(), safe="")
        url = f"https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true"
        payload = self.http.get_json(url)
        jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
        results: list[DiscoveryPosting] = []
        for job in jobs:
            if not isinstance(job, dict) or job.get("isListed") is False:
                continue
            job_url = str(job.get("jobUrl") or "").strip()
            title = str(job.get("title") or "").strip()
            description = str(job.get("descriptionPlain") or "").strip()
            if not description:
                description = html_to_text(job.get("descriptionHtml"))
            external_id = job_url or str(job.get("applyUrl") or "").strip()
            if not external_id or not title or not description:
                continue

            compensation = job.get("compensation") or {}
            compensation_text = None
            if isinstance(compensation, dict):
                compensation_text = (
                    compensation.get("scrapeableCompensationSalarySummary")
                    or compensation.get("compensationTierSummary")
                )
            location = str(job.get("location") or "").strip() or None
            if not location:
                address = ((job.get("address") or {}).get("postalAddress") or {})
                city = address.get("addressLocality")
                region = address.get("addressRegion")
                if city and region:
                    location = f"{city}, {region}"
                elif city:
                    location = str(city)

            results.append(
                DiscoveryPosting(
                    provider=self.provider,
                    external_id=external_id,
                    company=source.company,
                    title=title,
                    location=location,
                    work_arrangement=str(job.get("workplaceType") or "").strip() or None,
                    compensation_text=str(compensation_text).strip() if compensation_text else None,
                    description_raw=description,
                    source_url=job.get("jobUrl"),
                    apply_url=job.get("applyUrl"),
                    published_at=_parse_dt(job.get("publishedAt")),
                    employment_type=str(job.get("employmentType") or "").strip() or None,
                )
            )
        return results


class AdapterRegistry:
    def __init__(self, http: JsonHttpClient | None = None) -> None:
        self._adapters: dict[DiscoveryProvider, DiscoveryAdapter] = {
            DiscoveryProvider.GREENHOUSE: GreenhouseAdapter(http),
            DiscoveryProvider.LEVER: LeverAdapter(http),
            DiscoveryProvider.ASHBY: AshbyAdapter(http),
        }

    def get(self, provider: DiscoveryProvider) -> DiscoveryAdapter:
        return self._adapters[provider]
