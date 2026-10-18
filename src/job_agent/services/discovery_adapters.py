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
            "User-Agent": "job-agent-discovery/0.4.6 (+personal job-search automation)",
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

    def enrich(self, source: DiscoverySourceSummary, posting: DiscoveryPosting) -> DiscoveryPosting:
        """Optionally enrich a prefiltered posting without expanding the initial board scan."""
        return posting


class GreenhouseAdapter(DiscoveryAdapter):
    provider = DiscoveryProvider.GREENHOUSE

    def enrich(self, source: DiscoverySourceSummary, posting: DiscoveryPosting) -> DiscoveryPosting:
        if posting.compensation_text:
            return posting
        token = quote(source.board_identifier.strip(), safe="")
        job_id = quote(posting.external_id.strip(), safe="")
        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{job_id}?pay_transparency=true"
        try:
            payload = self.http.get_json(url)
        except Exception:
            return posting
        ranges = payload.get("pay_input_ranges", []) if isinstance(payload, dict) else []
        if not isinstance(ranges, list) or not ranges:
            return posting

        parsed: list[tuple[str, float, float, str]] = []
        for item in ranges:
            if not isinstance(item, dict):
                continue
            try:
                low = float(item.get("min_cents")) / 100.0
                high = float(item.get("max_cents")) / 100.0
            except (TypeError, ValueError):
                continue
            if low <= 0 or high <= 0:
                continue
            title = str(item.get("title") or "").strip()
            currency = str(item.get("currency_type") or "USD").upper()
            parsed.append((title, min(low, high), max(low, high), currency))
        if not parsed:
            return posting

        salary_like = [
            item for item in parsed
            if any(token in item[0].lower() for token in ("salary", "base", "pay"))
        ]
        selected = salary_like or parsed
        usd = [item for item in selected if item[3] == "USD"] or selected
        low = min(item[1] for item in usd)
        high = max(item[2] for item in usd)
        currency = usd[0][3]
        compensation = f"{currency} ${low:,.0f} - ${high:,.0f} base"
        return posting.model_copy(update={"compensation_text": compensation})

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

            compensation_text = None
            metadata = job.get("metadata")
            if isinstance(metadata, list):
                pay_parts: list[str] = []
                for item in metadata:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name") or "").strip()
                    value = item.get("value")
                    if name and any(token in name.lower() for token in ("salary", "compensation", "pay range", "base pay")):
                        if isinstance(value, dict):
                            pay_parts.append(f"{name}: {value}")
                        elif value not in (None, ""):
                            pay_parts.append(f"{name}: {value}")
                if pay_parts:
                    compensation_text = " | ".join(pay_parts)

            results.append(
                DiscoveryPosting(
                    provider=self.provider,
                    external_id=external_id,
                    company=source.company,
                    title=title,
                    location=str(location).strip() if location else None,
                    compensation_text=compensation_text,
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


class SmartRecruitersAdapter(DiscoveryAdapter):
    """Public SmartRecruiters Posting API. Fetch details only after title prefilter."""

    provider = DiscoveryProvider.SMARTRECRUITERS
    enrich_mandatory = True
    PAGE_SIZE = 100
    MAX_PAGES = 50

    @staticmethod
    def _location(info: dict) -> str | None:
        parts = [str(info.get(key) or "").strip() for key in ("city", "region")]
        return ", ".join(part for part in parts if part) or None

    def fetch(self, source: DiscoverySourceSummary) -> list[DiscoveryPosting]:
        identifier = quote(source.board_identifier.strip(), safe="")
        base_url = f"https://api.smartrecruiters.com/v1/companies/{identifier}/postings"
        results: list[DiscoveryPosting] = []
        seen_ids: set[str] = set()
        for page in range(self.MAX_PAGES):
            offset = page * self.PAGE_SIZE
            payload = self.http.get_json(f"{base_url}?limit={self.PAGE_SIZE}&offset={offset}")
            if not isinstance(payload, dict) or not isinstance(payload.get("content"), list):
                raise DiscoveryFetchError("SmartRecruiters returned an invalid postings payload")
            jobs = payload["content"]
            for job in jobs:
                if not isinstance(job, dict):
                    continue
                job_id = str(job.get("id") or "").strip()
                title = str(job.get("name") or "").strip()
                if not job_id or not title or job_id in seen_ids:
                    continue
                seen_ids.add(job_id)
                location = job.get("location") if isinstance(job.get("location"), dict) else {}
                results.append(
                    DiscoveryPosting(
                        provider=self.provider,
                        external_id=job_id,
                        company=source.company,
                        title=title,
                        location=self._location(location),
                        work_arrangement="remote" if location.get("remote") is True else None,
                        description_raw="Full job description will be retrieved after title filtering.",
                        published_at=_parse_dt(job.get("releasedDate")),
                    )
                )
            if "totalFound" not in payload:
                raise DiscoveryFetchError("SmartRecruiters omitted totalFound; cannot verify full board")
            try:
                total = int(payload["totalFound"])
            except (ValueError, TypeError) as exc:
                raise DiscoveryFetchError("Invalid SmartRecruiters totalFound") from exc
            if total < 0:
                raise DiscoveryFetchError("Invalid SmartRecruiters totalFound")
            if offset + len(jobs) >= total:
                return results
            if not jobs:
                raise DiscoveryFetchError("SmartRecruiters pagination ended before totalFound")
        raise DiscoveryFetchError("SmartRecruiters pagination exceeded configured maximum; no jobs closed")

    def enrich(self, source: DiscoverySourceSummary, posting: DiscoveryPosting) -> DiscoveryPosting:
        identifier = quote(source.board_identifier.strip(), safe="")
        job_id = quote(posting.external_id, safe="")
        url = f"https://api.smartrecruiters.com/v1/companies/{identifier}/postings/{job_id}"
        payload = self.http.get_json(url)
        if not isinstance(payload, dict):
            raise DiscoveryFetchError(f"Missing SmartRecruiters details for {posting.external_id}")
        sections = (payload.get("jobAd") or {}).get("sections") or {}
        parts = []
        if isinstance(sections, dict):
            for key in ("jobDescription", "qualifications", "additionalInformation", "companyDescription"):
                item = sections.get(key)
                if isinstance(item, dict):
                    content = html_to_text(item.get("text"))
                    if content:
                        parts.append(f"{item.get('title') or key}:\n{content}")
        description = "\n\n".join(parts)
        if len(description.strip()) < 30:
            raise DiscoveryFetchError(f"SmartRecruiters details incomplete for {posting.external_id}")
        loc = payload.get("location") if isinstance(payload.get("location"), dict) else {}
        apply_url = payload.get("applyUrl")
        job_url = payload.get("jobAdUrl") or apply_url
        if job_url and not str(job_url).startswith(("https://", "http://")):
            job_url = None
        if apply_url and not str(apply_url).startswith(("https://", "http://")):
            apply_url = None
        return posting.model_copy(update={
            "description_raw": description,
            "source_url": job_url,
            "apply_url": apply_url,
            "location": self._location(loc) or posting.location,
            "work_arrangement": "remote" if loc.get("remote") is True else posting.work_arrangement,
        })


class AdapterRegistry:
    def __init__(self, http: JsonHttpClient | None = None) -> None:
        self._adapters: dict[DiscoveryProvider, DiscoveryAdapter] = {
            DiscoveryProvider.GREENHOUSE: GreenhouseAdapter(http),
            DiscoveryProvider.LEVER: LeverAdapter(http),
            DiscoveryProvider.ASHBY: AshbyAdapter(http),
            DiscoveryProvider.SMARTRECRUITERS: SmartRecruitersAdapter(http),
        }

    def get(self, provider: DiscoveryProvider) -> DiscoveryAdapter:
        return self._adapters[provider]
