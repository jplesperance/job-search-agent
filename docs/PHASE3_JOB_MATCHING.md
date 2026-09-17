# Phase 3 — Deterministic Job Ingestion and Matching

Phase 3 adds an explainable job-analysis pipeline on top of the verified career-evidence retrieval service.

## Design goals

1. Treat job descriptions as untrusted external text.
2. Do not allow a job description to create or modify career evidence.
3. Canonicalize only skills already present in the approved career taxonomy.
4. Trace each positive requirement match to stable evidence keys.
5. Keep hard-filter decisions separate from fit scoring.
6. Persist the original JD, parsed requirements, targeting-policy version, score components, evidence keys, gaps, and unknowns.

## Pipeline

```text
Raw job description
        |
        v
Deterministic parser
        |
        +-- role family
        +-- seniority
        +-- work arrangement
        +-- requirements
        +-- known taxonomy skills
        |
        v
Hard filters (targeting policy)
        |
        v
Requirement-to-evidence matching
        |
        +-- USER_VERIFIED evidence only
        +-- approved evidence only
        +-- resume-safe evidence by default
        |
        v
Explainable weighted score
        |
        v
Persisted JobAnalysis
```

## What the parser will *not* do

The deterministic parser does not infer new skills or fabricate equivalence between unknown JD terminology and existing career evidence. A requirement that cannot be mapped to the taxonomy is preserved as an `unknown`, not silently treated as a gap or a match.

## Default scoring

- recognized requirement coverage: 60%
- target-title alignment: 15%
- seniority alignment: 10%
- role-family alignment: 15%

Required requirements have greater internal weight than preferred/context requirements.

The score is descriptive, not a decision to apply. `hard_filter_passed` remains a separate field.

## API

### Targeting policies

- `GET /api/v1/targeting-policies`
- `POST /api/v1/targeting-policies`
- `GET /api/v1/targeting-policies/{policy_id}`
- `POST /api/v1/targeting-policies/activate`

### Jobs

- `POST /api/v1/jobs/ingest`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `GET /api/v1/jobs/{job_id}/requirements`
- `POST /api/v1/jobs/{job_id}/analyze`
- `GET /api/v1/jobs/{job_id}/analyses/latest`

## CLI workflow

```bash
PYTHONPATH=src alembic upgrade head
PYTHONPATH=src python scripts/verify_phase3.py

# Edit this policy first.
cp data/examples/targeting_policy.example.json /tmp/my-policy.json
$EDITOR /tmp/my-policy.json
PYTHONPATH=src python scripts/create_targeting_policy.py /tmp/my-policy.json

PYTHONPATH=src python scripts/ingest_job.py /tmp/job.txt \
  --company "Example Corp" \
  --title "Principal Application Security Architect" \
  --location "Remote"

PYTHONPATH=src python scripts/analyze_job.py <JOB_UUID>
```
