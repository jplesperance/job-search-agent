# Phase 4.3 — Manual Job Intake

**Release:** `0.4.7`  
**Required base:** working Phase 4.2 (`0.4.6`)  
**Database:** no new migration; keep Alembic at **`0009`**  
**Impact:** all Phase 4.2 scheduled discovery, ATS watchlist, source health, canonical postings, Pushover configuration, and historical notification records are preserved.

## Scope

- New CLI: `scripts/import_job_url.py`
- New API: `POST /api/v1/jobs/manual-intake`
- A single manual submission can use a job-page URL or a local plain-text description.
- Recognized public Greenhouse, Lever, Ashby and SmartRecruiters URLs are first attempted through their public single-posting/board API. Other sites use schema.org `JobPosting` JSON-LD, then a constrained HTML job-content fallback. Protected/JavaScript-driven pages require pasted text.
- Reuses existing `JobIngestionService`, canonical `JobSourcePostingRow` and `JobMatchService`, even for roles below match score 80 or roles failing hard filters.
- Manual intake writes a Pushover `notification_states` suppression row for a canonical job unless there is already a sent/suppressed row. It does **not** send a push. If a previous notification was pending/failed, the submission suppresses it. The nightly/four-hour discovery scheduler remains unchanged.
- The URL retriever allows only public HTTPS/443, validates and IP-pins DNS per hop (including redirects), validates TLS for the original hostname, and limits response body to 2 MB, redirects to 3, and request timeout to 12 seconds. It does not execute scripts or interact with authenticated pages.

## Upgrade

Stop the timer while updating to avoid a source-tree change mid-run (the timer configuration itself is unchanged):

```bash
cd ~/job-search-agent
source .venv/bin/activate
sudo systemctl stop job-agent-discovery.timer

# Strongly recommended: back up your repository and PostgreSQL database.
unzip -o /path/to/job-agent-phase4.3-manual-job-intake-patch-v0.4.7.zip -d .
pip install -e '.[dev]'
PYTHONPATH=src pytest -q
PYTHONPATH=src alembic current     # expect 0009 (head)
make verify-phase42

sudo systemctl start job-agent-discovery.timer
```

Expected clean merged-source suite: **118 passed**. No `alembic upgrade` is needed if your database is already at `0009`.

## Import a public job URL

```bash
PYTHONPATH=src python scripts/import_job_url.py \
  "https://jobs.smartrecruiters.com/ServiceNow/744000155745179-staff-applied-security-engineer"
```

When the public API does not carry a company name, the importer looks up the ATS board identifier in your configured `discovery_sources`. For a board not configured in the watchlist, specify `--company` (and `--title` if the page lacks a title):

```bash
PYTHONPATH=src python scripts/import_job_url.py \
  "https://jobs.example.com/careers/role123" \
  --company "Example Corp" \
  --title "Director of Application Security"
```

### Locked, JavaScript-only, or otherwise inaccessible pages

Copy the complete job description into a UTF-8 text file and use:

```bash
PYTHONPATH=src python scripts/import_job_url.py \
  "https://www.linkedin.com/jobs/view/123456789/" \
  --text-file /tmp/job-description.txt \
  --company "Example Corp" \
  --title "Director of Application Security" \
  --location "Remote"
```

With `--text-file`, the tool **does not make a network request** to the supplied URL. If you only have text, omit the URL:

```bash
PYTHONPATH=src python scripts/import_job_url.py \
  --text-file /tmp/job-description.txt \
  --company "Example Corp" \
  --title "Director of Application Security"
```

The importer returns the canonical `job_id`, an indication of whether the record was already present, all hard-filter outcomes, the match score, requirement coverage, and Pushover suppression status as JSON. A manual role is always analyzed, regardless of score.

## API submission

`POST /api/v1/jobs/manual-intake` with either:

```json
{"source_url":"https://jobs.example.com/role/123"}
```

Or text and optional URL (no fetch when text is supplied):

```json
{
  "source_url": "https://www.linkedin.com/jobs/view/123456789/",
  "company": "Example Corp",
  "title": "Director of Application Security",
  "location": "Remote",
  "description_raw": "[complete pasted job description, minimum 80 characters]"
}
```

The endpoint returns `ingestion`, `analysis`, `extraction_method`, `canonical_duplicate`, and `notification_suppressed`. Validation or extraction errors return HTTP 422 with an actionable message. An inactive or missing targeting policy returns HTTP 409. Ensure your API is restricted to trusted users: job submissions change the career database and can fetch public URLs.

## Behavior and limitations

- A manually added record is labeled `manual:url` or `manual:text`, with a stable source external ID. The canonicalization algorithm remains the existing Phase 4.1 algorithm. If the same job is already in discovery, it is linked to the existing canonical job, not duplicated where identity is confidently established.
- No discovery source, posting closure, health incident, or job notification is generated by manual intake.
- No automatic retry, persistent URL watch, or periodic re-fetch is created; manual submissions are one-time snapshots. Existing automated discovery continues independently.
- Deduplication is conservative, not infallible; distinct requisitions can share descriptions, and radically different URLs can point to the same job. Verify ambiguous cases manually before tailoring.
- A failure to retrieve complete public posting text is *not* treated as a job description. Supply `--text-file` instead. LinkedIn and some employer websites may be authenticated, JavaScript-rendered, or inaccessible to simple HTTP clients.
- Some external pages omit compensation or provide non-base figures. Missing compensation still receives normal manual review under your current policies.
- The underlying site and ATS API may have independent service-use restrictions; use the importer only for job postings you are authorized to access.

### Smoke test

Use a posting already discovered through the watchlist. The response should indicate `canonical_duplicate=true`, the same canonical `job_id` as before, and a match analysis. Check that `notification_states` has one `pushover/new_match` record for the canonical job and that `make recent-matches` does not duplicate the opportunity. Import the URL a second time to verify idempotency. Then check `make discovery-health` and the timer's status.
