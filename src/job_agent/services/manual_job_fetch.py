"""Public HTTPS job-page retrieval with DNS/IP pinning and conservative extraction.

This module intentionally does not run Javascript, use a browser, or read internal URLs.
Unsupported pages require a pasted job description instead of guessing.
"""
from __future__ import annotations

import http.client
import ipaddress
import json
import re
import socket
import ssl
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit

from job_agent.services.discovery_adapters import html_to_text

MAX_RESPONSE_BYTES = 2_000_000
MAX_REDIRECTS = 3
MAX_DESCRIPTION_CHARS = 120_000


class ManualFetchError(ValueError):
    """Unsupported or unsafe job URL; the user can submit the description as text."""


@dataclass(frozen=True)
class FetchedJob:
    source_url: str
    company: str | None
    title: str | None
    location: str | None
    compensation_text: str | None
    description_raw: str
    extraction_method: str
    ats_provider: str | None = None
    ats_board: str | None = None


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connect only to the vetted address while verifying TLS for the DNS hostname."""

    def __init__(self, hostname: str, ip: str, timeout: float) -> None:
        super().__init__(hostname, port=443, timeout=timeout, context=ssl.create_default_context())
        self._vetted_ip = ip

    def connect(self) -> None:
        connection = socket.create_connection((self._vetted_ip, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(connection, server_hostname=self.host)
        except Exception:
            connection.close()
            raise


def _public_host(url: str) -> tuple[str, str, str]:
    """Validate every redirect hop and resolve DNS before connecting.

    Reject *any* non-global address returned for a hostname. Resolve again for
    each request, but connect to a vetted IP rather than resolving twice.
    """
    if len(url) > 4096 or any(ord(char) < 32 or ord(char) == 127 for char in url):
        raise ManualFetchError("Unsafe or excessively long job URL")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise ManualFetchError("Invalid job URL") from exc
    if parts.scheme.lower() != "https" or not parts.hostname or port not in (None, 443):
        raise ManualFetchError("Only public HTTPS job URLs on port 443 are supported")
    if parts.username is not None or parts.password is not None:
        raise ManualFetchError("Credentials in job URLs are not permitted")
    host = parts.hostname.rstrip(".")
    if not host or host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ManualFetchError("Local or internal job URLs are not permitted")
    try:
        ipaddress.ip_address(host)
        raise ManualFetchError("Direct IP address job URLs are not permitted")
    except ValueError as exc:
        if isinstance(exc, ManualFetchError):
            raise
    try:
        host_ascii = host.encode("idna").decode("ascii")
        if not re.fullmatch(r"[a-zA-Z0-9.-]+", host_ascii):
            raise ValueError("Invalid hostname")
        addresses = socket.getaddrinfo(host_ascii, 443, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ManualFetchError("Job URL host could not be safely resolved") from exc
    ips = sorted({entry[4][0] for entry in addresses})
    if not ips or not all(ipaddress.ip_address(ip).is_global for ip in ips):
        raise ManualFetchError("Job URL resolves to a private, reserved, or unreachable address")
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    return host_ascii, ips[0], path


def fetch_public_page(url: str, *, timeout: float = 12.0, allow_json: bool = False) -> tuple[str, str, str]:
    """Return (final URL, document text, MIME type), with each hop IP-pinned."""
    current = url
    for attempt in range(MAX_REDIRECTS + 1):
        host, ip, path = _public_host(current)
        connection = _PinnedHTTPSConnection(host, ip, timeout)
        try:
            connection.request(
                "GET", path,
                headers={
                    "Host": host,
                    "Accept": "application/json" if allow_json else "text/html, application/xhtml+xml, text/plain",
                    "Accept-Encoding": "identity",
                    "User-Agent": "job-agent-manual-intake/0.4.7",
                },
            )
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location:
                    raise ManualFetchError("Job page redirected without a Location header")
                if attempt >= MAX_REDIRECTS:
                    raise ManualFetchError("Job URL exceeded maximum redirects")
                current = urljoin(current, location)
                continue
            if response.status != 200:
                raise ManualFetchError(f"Job URL returned HTTP {response.status}; paste the job description")
            if response.getheader("Content-Encoding", "identity").casefold() not in {"", "identity"}:
                raise ManualFetchError("Compressed page not supported; paste the job description")
            mime = response.getheader("Content-Type", "").partition(";")[0].strip().lower()
            accepted = {"application/json"} if allow_json else {"text/html", "application/xhtml+xml", "text/plain"}
            if mime not in accepted:
                raise ManualFetchError("Job URL returned an unsupported content type; paste the job description")
            length = response.getheader("Content-Length")
            if length and length.isdigit() and int(length) > MAX_RESPONSE_BYTES:
                raise ManualFetchError("Job page exceeds the maximum permitted size")
            content = response.read(MAX_RESPONSE_BYTES + 1)
            if len(content) > MAX_RESPONSE_BYTES:
                raise ManualFetchError("Job page exceeds the maximum permitted size")
            charset = "utf-8"
            content_type = response.getheader("Content-Type", "")
            match = re.search(r"charset\s*=\s*['\"]?([a-zA-Z0-9_-]+)", content_type, re.I)
            if match:
                charset = match.group(1)
            try:
                decoded = content.decode(charset, errors="replace")
            except LookupError:
                decoded = content.decode("utf-8", errors="replace")
            return current, decoded, mime
        except (socket.timeout, OSError, ssl.SSLError, http.client.HTTPException) as exc:
            raise ManualFetchError("Unable to retrieve job URL; paste the description manually") from exc
        finally:
            connection.close()
    raise ManualFetchError("Could not retrieve the job URL")


class _PageExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.json_scripts: list[str] = []
        self.meta: dict[str, str] = {}
        self.headings: list[str] = []
        self.main_text: list[str] = []
        self._script: list[str] | None = None
        self._main_depths: list[int] = []
        self._stack: list[str] = []
        self._ignored_level = 0
        self._inside_script = False
        self._h1_level = 0
        self._h1_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attrs_map = dict(attrs)
        tag = tag.lower()
        if tag not in {"meta", "link", "br", "img", "input", "hr", "source", "area", "base", "embed", "wbr"}:
            self._stack.append(tag)
        if tag == "meta":
            key = (attrs_map.get("property") or attrs_map.get("name") or "").lower()
            if key and attrs_map.get("content"):
                self.meta[key] = attrs_map["content"]
        if tag == "script":
            self._inside_script = True
            if "ld+json" in (attrs_map.get("type") or "").lower():
                self._script = []
        if tag == "h1":
            self._h1_level += 1
            self._h1_parts = []
        if tag in {"header", "footer", "nav", "aside", "style", "noscript"}:
            self._ignored_level += 1
        if tag in {"main", "article"} or (
            tag in {"section", "div"} and re.search(
                r"job[-_ ]?(description|details|content)",
                (attrs_map.get("id") or "") + " " + (attrs_map.get("class") or ""), re.I
            )
        ):
            self._main_depths.append(len(self._stack))
        if self._main_depths and not self._ignored_level and tag in {"p", "div", "li", "br", "h1", "h2", "h3", "h4"}:
            self.main_text.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "script":
            self._inside_script = False
            if self._script is not None:
                self.json_scripts.append("".join(self._script))
                self._script = None
        if tag == "h1" and self._h1_level:
            text = " ".join("".join(self._h1_parts).split())
            if text:
                self.headings.append(text)
            self._h1_level -= 1
        if tag in {"header", "footer", "nav", "aside", "style", "noscript"} and self._ignored_level:
            self._ignored_level -= 1
        if tag in self._stack:
            index = len(self._stack) - 1 - self._stack[::-1].index(tag)
            del self._stack[index:]
            while self._main_depths and self._main_depths[-1] > len(self._stack):
                self._main_depths.pop()

    def handle_data(self, data: str) -> None:
        if self._script is not None:
            self._script.append(data)
        if self._h1_level:
            self._h1_parts.append(data)
        if self._main_depths and not self._ignored_level and not self._inside_script:
            self.main_text.append(data)


def _find_jobposting(value: object) -> dict | None:
    if isinstance(value, list):
        return next((j for item in value if (j := _find_jobposting(item))), None)
    if not isinstance(value, dict):
        return None
    types = value.get("@type", "")
    if types == "JobPosting" or (isinstance(types, list) and "JobPosting" in types):
        return value
    for key in ("@graph", "mainEntity"):
        if (found := _find_jobposting(value.get(key))) is not None:
            return found
    return None


def _job_location(value: object) -> str | None:
    if isinstance(value, list):
        return ", ".join(v for item in value if (v := _job_location(item))) or None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        address = value.get("address", value)
        if isinstance(address, str):
            return address.strip() or None
        if isinstance(address, dict):
            return ", ".join(str(address[key]) for key in ("addressLocality", "addressRegion", "addressCountry") if address.get(key)) or None
    return None


def _base_salary(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    currency = value.get("currency", "USD")
    unit = value.get("value", value)
    if isinstance(unit, dict):
        low = unit.get("minValue", unit.get("value"))
        high = unit.get("maxValue", unit.get("value"))
        unit_type = unit.get("unitText", "YEAR")
    else:
        low = high = unit
        unit_type = "YEAR"
    if currency == "USD" and str(unit_type).upper() in {"YEAR", "ANNUAL"}:
        try:
            return f"${float(low):,.0f} - ${float(high):,.0f} base"
        except (TypeError, ValueError):
            pass
    return None


def extract_job_page(url: str, html: str, mime: str = "text/html") -> FetchedJob:
    if mime == "text/plain":
        desc = html.strip()
        if len(desc) < 80:
            raise ManualFetchError("Job description too short; paste a complete posting")
        return FetchedJob(url, None, None, None, None, desc[:MAX_DESCRIPTION_CHARS], "plain_text")

    parser = _PageExtractor()
    parser.feed(html)
    for raw in parser.json_scripts:
        try:
            job = _find_jobposting(json.loads(raw))
        except (ValueError, TypeError):
            continue
        if not job:
            continue
        description = html_to_text(str(job.get("description") or ""))
        if len(description) < 80:
            continue
        company = job.get("hiringOrganization")
        if isinstance(company, dict):
            company = company.get("name")
        elif not isinstance(company, str):
            company = None
        arrangement = job.get("jobLocationType")
        location = "Remote" if isinstance(arrangement, str) and "TELECOMMUTE" in arrangement.upper() else _job_location(job.get("jobLocation"))
        return FetchedJob(
            url, str(company) if company else None,
            str(job.get("title")) if job.get("title") else None,
            location, _base_salary(job.get("baseSalary")),
            description[:MAX_DESCRIPTION_CHARS], "json_ld",
        )
    main = "\n".join(" ".join(x.split()) for x in "".join(parser.main_text).splitlines() if x.strip())
    if len(main) < 120:
        raise ManualFetchError("Job page lacks an accessible full description; paste the posting")
    title = parser.headings[0] if parser.headings else parser.meta.get("og:title")
    company = parser.meta.get("og:site_name")
    if company and company.lower() in {"greenhouse", "lever", "ashby", "linkedin", "smartrecruiters"}:
        company = None
    return FetchedJob(url, company, title, None, None, main[:MAX_DESCRIPTION_CHARS], "html_main")


def _api_json(url: str) -> object:
    _, raw, _ = fetch_public_page(url, allow_json=True)
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise ManualFetchError("ATS API returned invalid JSON") from exc


def _ats_job(url: str) -> FetchedJob | None:
    """Use public official ATS endpoints for recognized posting URL patterns.

    We never trust user text to select an arbitrary API host. Unsupported ATS
    pages fall back to conservative HTML/JSON-LD extraction.
    """
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    path = [segment for segment in parts.path.split("/") if segment]
    if not path:
        return None

    if host in {"boards.greenhouse.io", "job-boards.greenhouse.io"} and len(path) >= 3 and path[1] == "jobs":
        board, job_id = path[0], path[2]
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", board) or not re.fullmatch(r"[0-9]+", job_id):
            return None
        data = _api_json(f"https://boards-api.greenhouse.io/v1/boards/{quote(board)}/jobs/{job_id}?content=true")
        if isinstance(data, dict):
            description = html_to_text(data.get("content"))
            location = data.get("location") or {}
            if len(description) >= 80 and data.get("title"):
                return FetchedJob(
                    url, None, str(data["title"]), location.get("name") if isinstance(location, dict) else None,
                    None, description[:MAX_DESCRIPTION_CHARS], "greenhouse_api", "greenhouse", board,
                )

    elif host in {"jobs.lever.co", "jobs.eu.lever.co"} and len(path) >= 2:
        board, job_id = path[0], path[1]
        if not all(re.fullmatch(r"[a-zA-Z0-9_-]+", token) for token in (board, job_id)):
            return None
        api_host = "api.eu.lever.co" if host == "jobs.eu.lever.co" else "api.lever.co"
        data = _api_json(f"https://{api_host}/v0/postings/{quote(board)}/{quote(job_id)}")
        if isinstance(data, dict):
            description = str(data.get("descriptionPlain") or "").strip()
            for item in data.get("lists") or []:
                if isinstance(item, dict):
                    description += "\n\n" + str(item.get("text") or "") + "\n" + html_to_text(item.get("content"))
            description += "\n\n" + str(data.get("additionalPlain") or "")
            categories = data.get("categories") or {}
            if len(description.strip()) >= 80 and data.get("text"):
                return FetchedJob(
                    url, None, str(data["text"]), categories.get("location") if isinstance(categories, dict) else None,
                    str(data.get("salaryDescriptionPlain")) if data.get("salaryDescriptionPlain") else None,
                    description.strip()[:MAX_DESCRIPTION_CHARS], "lever_api", "lever", board,
                )

    elif host == "jobs.ashbyhq.com" and len(path) >= 2:
        board = path[0]
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", board):
            return None
        data = _api_json(f"https://api.ashbyhq.com/posting-api/job-board/{quote(board)}?includeCompensation=true")
        if isinstance(data, dict):
            from job_agent.services.canonical_jobs import normalize_source_url
            target = normalize_source_url(url)
            target_path = urlsplit(url).path.rstrip("/")
            for item in data.get("jobs") or []:
                if not isinstance(item, dict):
                    continue
                job_url = str(item.get("jobUrl") or "")
                # Exact link or path identity; do not guess by title.
                if normalize_source_url(job_url) != target and urlsplit(job_url).path.rstrip("/") != target_path:
                    continue
                description = str(item.get("descriptionPlain") or "").strip() or html_to_text(item.get("descriptionHtml"))
                compensation = item.get("compensation") or {}
                compensation_text = (compensation.get("scrapeableCompensationSalarySummary") or compensation.get("compensationTierSummary")) if isinstance(compensation, dict) else None
                if len(description) >= 80 and item.get("title"):
                    return FetchedJob(
                        url, None, str(item["title"]), item.get("location"),
                        str(compensation_text) if compensation_text else None, description[:MAX_DESCRIPTION_CHARS],
                        "ashby_api", "ashby", board,
                    )

    elif host == "jobs.smartrecruiters.com" and len(path) >= 2:
        board = path[0]
        match = re.match(r"([0-9]+)(?:-|$)", path[1])
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", board) or not match:
            return None
        data = _api_json(f"https://api.smartrecruiters.com/v1/companies/{quote(board)}/postings/{match.group(1)}")
        if isinstance(data, dict):
            sections = ((data.get("jobAd") or {}).get("sections") or {})
            description = "\n\n".join(
                html_to_text((sections.get(key) or {}).get("text"))
                for key in ("jobDescription", "qualifications", "additionalInformation")
                if isinstance(sections.get(key), dict)
            )
            location = data.get("location") or {}
            loc = ", ".join(str(location[key]) for key in ("city", "region") if location.get(key)) if isinstance(location, dict) else None
            if len(description) >= 80 and data.get("name"):
                return FetchedJob(
                    url, None, str(data["name"]), loc, None, description[:MAX_DESCRIPTION_CHARS],
                    "smartrecruiters_api", "smartrecruiters", board,
                )
    return None


def retrieve_job(url: str) -> FetchedJob:
    # Validate the original URL even if an ATS API will retrieve the description.
    _public_host(url)
    try:
        ats_job = _ats_job(url)
        if ats_job is not None:
            return ats_job
    except ManualFetchError:
        # A public job board can transiently fail its API while exposing usable HTML.
        pass
    final_url, html, mime = fetch_public_page(url)
    return extract_job_page(final_url, html, mime)
