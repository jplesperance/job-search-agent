# Job Agent System

Security-conscious, human-governed multi-agent job-search platform.

## Phase 1 scope

Phase 1 builds the system of record and decision foundation:

1. Canonical career knowledge base
2. Job targeting preferences and hard constraints
3. Deterministic + semantic job scoring contract
4. Application state model and audit event log
5. Repository/service boundaries for later agents

Phase 1 deliberately does **not** include LinkedIn/browser automation, email monitoring, or autonomous job submission.

## Architectural principles

- PostgreSQL is the source of truth.
- Agents operate on structured contracts; they do not own durable state.
- Career claims must trace back to approved evidence items.
- Every application status change becomes an immutable event.
- Side-effecting actions introduced in later phases require explicit policy/approval controls.
- External integrations are adapters behind service boundaries.

## Quick start

```bash
cp .env.example .env
docker compose up -d db
python -m venv .venv
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
pytest
```

## Repository layout

See `docs/system-design.md` and `docs/phase-1.md`.
