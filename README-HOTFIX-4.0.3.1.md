# Phase 4.0.3.1 FastAPI route-test hotfix

This hotfix updates only `tests/test_api_routes.py`.

FastAPI 0.137+ changed `include_router()` internals so `app.routes` may contain
`_IncludedRouter` objects that do not expose `.path` or `.methods`. The old test
iterated `app.routes` directly and therefore raised `AttributeError` on newer
FastAPI versions.

The replacement test validates the application's documented routes through
`app.openapi()`, which is the public API contract and does not depend on FastAPI
router internals.

No database migration, application code, targeting policy, or discovery changes
are included.

Apply from the repository root:

```bash
unzip -o /path/to/job-agent-phase4-fastapi-route-test-hotfix-v0.4.3.1.zip -d .
source .venv/bin/activate
PYTHONPATH=src pytest -q
```
