# Phase 3.1 — Deterministic Job Ingestion, Matching, and Commute-Aware Compensation

Phase 3.1 extends the evidence-grounded job-analysis pipeline with deterministic geography and compensation rules.

## Design goals

1. Treat job descriptions as untrusted external text.
2. Do not allow a JD to create or modify career evidence.
3. Canonicalize only skills already present in the approved career taxonomy.
4. Trace each positive requirement match to stable evidence keys.
5. Keep hard-filter decisions separate from fit scoring.
6. Persist the original JD, parsed requirements, targeting-policy version, score components, evidence keys, gaps, unknowns, and location/compensation decision.
7. Apply different base-salary floors based on commute burden.
8. Avoid false rejections when salary or exact Bay Area city is missing.

## Location/compensation policy

Fully remote uses its own floor. Non-remote jobs are normalized against configured commute-zone city lists.

| Rule | Minimum base |
|---|---:|
| Fully remote | $275,000 |
| Zone A | $275,000 |
| Zone B | $300,000 |
| Zone C | $325,000 |

A posting fails the salary hard filter only when a published maximum is available and is below the applicable floor. Missing salary is marked `manual_review_required=true`.

Non-remote positions in a clearly identified city outside the configured SF Bay Area zones fail the location hard filter. Generic local locations such as `Bay Area`, `San Francisco Bay Area`, `Silicon Valley`, or missing city are retained for manual review.

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
Location + compensation evaluator
        |
        +-- remote vs non-remote
        +-- normalized city
        +-- commute zone
        +-- applicable base floor
        +-- published max base
        +-- manual-review flag
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

`JobMatchResponse.location_compensation` exposes the exact rule decision used for the analysis.

## Upgrade workflow

```bash
PYTHONPATH=src alembic upgrade head
PYTHONPATH=src pytest -q
make verify-phase3
PYTHONPATH=src python scripts/create_targeting_policy.py \
  data/examples/targeting_policy.example.json
```
