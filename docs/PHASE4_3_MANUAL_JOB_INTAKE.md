# Phase 4.3: One pipeline, two ingestion entry points

### Existing scheduled mode

Provider adapters -> normalized job -> canonical `job_opportunities` -> per-source `job_source_postings` -> parser -> policy match -> alert ledger.

### New manual mode

Operator supplies URL and/or pasted description -> public ATS API or JSON-LD or HTML main-content extractor -> normalized `JobIngestRequest` -> **same** canonical `SqlAlchemyJobRepository.upsert` -> **same** deterministic parser -> **same** `JobMatchService.analyze` -> Pushover suppression ledger, no outbound alert.

### Interfaces

- CLI `PYTHONPATH=src python scripts/import_job_url.py <url> [--company ... --title ... --text-file ...]`
- API `POST /api/v1/jobs/manual-intake`
- Pydantic types `ManualJobIntakeRequest` / `ManualJobIntakeResponse`
- Parser `manual_job_fetch.py` (public HTTPS only, DNS/IP pinning)
- Orchestrator `ManualJobIntakeService`

The database transaction commits **only after** ingestion, notification suppression, and analysis succeed. An exception rolls back all three through the existing FastAPI request unit-of-work or the CLI. No new Alembic tables.

### Follow-on (Phase 5)

The canonical `job_id` and evidence-backed `JobMatchResponse` become inputs to resume tailoring regardless of whether the opportunity came from an ATS scan or a submitted URL. Explicitly use `hard_filter_passed` and uncertainty fields to distinguish user-selected exceptions from automated recommendations.
