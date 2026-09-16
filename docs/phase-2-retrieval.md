# Phase 2: Deterministic Career Evidence Retrieval

Phase 2 adds the first read path over the authoritative PostgreSQL career knowledge base.

## Goals

- Preserve stable evidence keys (for example `TT-AISEC-001`) in PostgreSQL.
- Preserve verification status and resume-safety metadata as first-class columns.
- Resolve requested skills against the normalized skill taxonomy and aliases.
- Search approved evidence without an LLM.
- Return exact evidence claims, experience context, matched skills, and provenance controls.
- Give future agents a deterministic baseline before semantic/embedding retrieval is introduced.

## Retrieval scopes

- `general`: trusted/approved evidence, with caller-provided filters.
- `matching`: same data access behavior as general; intended for job-fit analysis where internal evidence can inform matching.
- `resume`: forces `resume_eligible=true` and limits visibility to `public_safe` or `generalize`.

`resume` scope is the safety boundary future Resume Agents should use.

## API

- `GET /health`
- `GET /api/v1/profile`
- `GET /api/v1/experiences`
- `GET /api/v1/experiences/{id}`
- `GET /api/v1/skills`
- `GET /api/v1/certifications`
- `GET /api/v1/evidence?skill=Threat%20Modeling&q=AI&limit=10`
- `GET /api/v1/evidence/{uuid-or-evidence-key}`
- `POST /api/v1/evidence/search`

Example POST body:

```json
{
  "skills": ["Application Security", "Threat Modeling", "AI/LLM Security"],
  "query": "AI threat modeling",
  "scope": "resume",
  "match_mode": "any",
  "limit": 20
}
```

## Database upgrade from v1.1

```bash
source .venv/bin/activate
PYTHONPATH=src alembic upgrade head
make seed-kb
```

The second command is intentionally repeated. The importer is idempotent and now backfills the retrieval metadata columns from the enriched v1.1 seed.

Verify:

```sql
SELECT count(*) FROM evidence_items WHERE evidence_key IS NOT NULL;
SELECT count(*) FROM evidence_items WHERE verification_status IS NOT NULL;
SELECT count(*) FROM evidence_items WHERE resume_eligible = true;
```

## CLI smoke test

```bash
PYTHONPATH=src python scripts/search_evidence.py \
  --skill "AI/LLM Security" \
  --skill "Threat Modeling" \
  --query "MITRE ATT&CK" \
  --scope resume \
  --limit 10
```

## Deliberately deferred

- pgvector / embeddings
- LLM reranking
- Job-description parsing
- Match scoring
- Resume generation

Those layers should build on and be tested against this deterministic baseline.
