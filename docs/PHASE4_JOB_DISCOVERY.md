# Phase 4 — Automated Job Discovery

Phase 4 polls public ATS job-board feeds, normalizes postings, prefilters for security-role titles, ingests the full job description, runs the existing deterministic matcher, and persists the results.

## Supported sources

### Greenhouse

Configure the public board token from a board URL/API path. Phase 4 calls:

`GET https://api.greenhouse.io/v1/boards/{TOKEN}/jobs?content=true`

The public Job Board API returns published posts and `content=true` includes the job description.

### Lever

Configure the Lever site name. Phase 4 calls:

`GET https://api.lever.co/v0/postings/{SITE}?mode=json`

The public Postings API returns published job data including plaintext descriptions, locations, workplace type, and optional salary ranges.

For EU-hosted Lever sites, set `config.region` to `eu`.

### Ashby

Configure the Ashby jobs page name. Phase 4 calls:

`GET https://api.ashbyhq.com/posting-api/job-board/{BOARD}?includeCompensation=true`

The public posting feed returns published jobs, plaintext descriptions, remote/hybrid/onsite metadata, and optional structured compensation.

## Processing pipeline

```text
Discovery source
    ↓
Public ATS adapter
    ↓
Normalized posting
    ↓
Security-title prefilter
    ↓
JobIngestionService
    ↓
Raw JD persisted + parsed
    ↓
JobMatchService
    ↓
Hard filters + evidence score
    ↓
Persist latest analysis
    ↓
Surface if hard filters pass and score >= threshold
```

All security-title candidates are retained even if they fail a hard filter or score below the surfacing threshold. This allows later parser/matcher releases to rescore historical jobs.

## Source configuration

Each source contains:

- `company`
- `provider`: `greenhouse`, `lever`, or `ashby`
- `board_identifier`
- `enabled`
- `priority`
- provider-specific `config`

Example:

```json
{
  "company": "Example Corp",
  "provider": "greenhouse",
  "board_identifier": "examplecorp",
  "enabled": true,
  "priority": 100,
  "config": {}
}
```

## CLI

Add one source:

```bash
PYTHONPATH=src python scripts/add_discovery_source.py \
  --company "Example Corp" \
  --provider greenhouse \
  --identifier examplecorp
```

Load a JSON array of sources:

```bash
PYTHONPATH=src python scripts/load_discovery_sources.py sources.json
```

Run all enabled sources:

```bash
PYTHONPATH=src python scripts/run_discovery.py --all
```

Run one source:

```bash
PYTHONPATH=src python scripts/run_discovery.py --source-id <UUID>
```

List surfaced candidates:

```bash
PYTHONPATH=src python scripts/list_discovery_candidates.py --minimum-score 80
```

## API

- `POST /api/v1/discovery/sources`
- `GET /api/v1/discovery/sources`
- `POST /api/v1/discovery/run`
- `GET /api/v1/discovery/runs`
- `GET /api/v1/discovery/candidates`

## Closure detection

After a successful board poll, previously open jobs for that source that are no longer returned are marked `closed`. Failed board fetches do not close jobs.

## LinkedIn

Phase 4 does not scrape LinkedIn. LinkedIn discovery should be implemented later through job-alert email ingestion or other permitted integrations and normalized into the same `JobIngestRequest` path.
