# Job Agent System — Phase 4.0.2

# Job Agent System — Phase 4

Human-governed job-search system with a verified career evidence base, deterministic job matching, commute-aware compensation filters, and automated public-ATS job discovery.

## Phase 4 capabilities

- polls public Greenhouse, Lever, and Ashby job boards
- preserves the complete JD for deterministic parsing and later re-analysis
- stores ATS-native remote/hybrid/onsite metadata
- uses a broad security-title prefilter before expensive evidence matching
- deduplicates by provider board + external posting ID
- automatically runs Phase 3.2.1 evidence matching
- keeps low-scoring and hard-filter-failed security jobs for historical rescoring
- records discovery-run counts/errors for auditability
- marks postings closed when they disappear from a successfully polled board
- exposes ranked, currently open candidates through CLI and FastAPI

No LLM is required for discovery or matching in Phase 4.

## Upgrade from Phase 3.2.1

```bash
source .venv/bin/activate
pip install -e '.[dev]'
PYTHONPATH=src alembic upgrade head
PYTHONPATH=src pytest -q
make verify-phase4
```

Expected migration head: `0006`.

## Add discovery sources

One source:

```bash
PYTHONPATH=src python scripts/add_discovery_source.py \
  --company "Example Corp" \
  --provider greenhouse \
  --identifier examplecorp
```

Or load a JSON array based on `data/examples/discovery_sources.example.json`:

```bash
PYTHONPATH=src python scripts/load_discovery_sources.py /path/to/sources.json
```

## Run discovery

```bash
PYTHONPATH=src python scripts/run_discovery.py --all --minimum-score 80
```

Then:

```bash
PYTHONPATH=src python scripts/list_discovery_candidates.py --minimum-score 80
```

## API

Run the API:

```bash
make run
```

Discovery endpoints:

```text
POST /api/v1/discovery/sources
GET  /api/v1/discovery/sources
POST /api/v1/discovery/run
GET  /api/v1/discovery/runs
GET  /api/v1/discovery/candidates
```

Existing career-evidence, targeting-policy, job-ingestion, and job-analysis endpoints remain available.

See `docs/PHASE4_JOB_DISCOVERY.md` for the discovery pipeline and `docs/PHASE3_JOB_MATCHING.md` for matching details.

## Phase 4.0.1 role-preference calibration

Phase 4.0.1 adds policy-driven exclusion of software-engineering and coding-heavy roles, strengthens the security-title gate, improves salary extraction from ATS text, and deduplicates same-board postings before analysis. See `README-PHASE4.0.1-UPGRADE.md`.
