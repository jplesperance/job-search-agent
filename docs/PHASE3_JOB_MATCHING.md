# Phase 3.2 — Deterministic JD Interpretation and Evidence-Grounded Matching

Phase 3.2 keeps matching deterministic while improving how real job descriptions are interpreted.

## Design goals

1. Preserve the entire raw JD as untrusted source text.
2. Separate requirements, preferred qualifications, responsibilities, compensation, benefits, and boilerplate.
3. Never let a JD create career evidence.
4. Trace positive skill matches to stable evidence keys.
5. Treat explicit gaps differently from parser uncertainty.
6. Evaluate tenure requirements from verified career chronology/evidence rather than keywords alone.
7. Support `any` semantics for requirements phrased as alternatives.
8. Persist enough metadata to reproduce why a score was produced.

## Pipeline

```text
Raw JD
  |
  +--> section segmentation
  |      +-- responsibilities
  |      +-- required qualifications
  |      +-- preferred qualifications
  |      +-- compensation (not a requirement)
  |      +-- benefits / EEO / boilerplate (ignored for fit)
  |
  +--> structured requirement parsing
  |      +-- skill
  |      +-- experience_years
  |      +-- leadership_years
  |      +-- operating_model
  |      +-- any/all skill semantics
  |
  +--> location + base-salary policy
  |
  +--> verified career-evidence retrieval
  |
  +--> requirement coverage + gaps + unknowns
  |
  +--> score + explicit confidence
  |
  +--> persisted JobAnalysis
```

## Score confidence

Unknown required qualifications are no longer silently excluded from the denominator. They are treated as unresolved uncertainty rather than definite failures.

`JobMatchResponse.confidence` reports:

- required total / recognized / matched / unknown
- preferred total / recognized / matched
- required recognition percentage
- required and preferred match percentages
- overall parser/match confidence
- whether manual requirement review is needed

The overall score receives a modest confidence adjustment so a poorly understood JD cannot present the same certainty as a fully parsed JD.

## Domain normalization added in 3.2

- AI/ML security -> `AI/LLM Security`
- PHI -> `Healthcare Security`
- PII -> `Privacy Engineering` + `Data Security`
- GRC -> `Security Governance` + `Risk Management` + `Compliance`
- SecOps / blue team -> `Security Monitoring` / `Incident Response`
- stakeholder communication -> existing business-risk / technical-consulting evidence
- frequent releases -> `Release Engineering`
- strategic + hands-on -> `Strategy` + `Technical Leadership`
- red team / penetration testing / bug bounty -> explicit `Offensive Security` concept

`Offensive Security` is intentionally a recognized virtual concept with no automatic evidence mapping in this release. That prevents the matcher from inflating dedicated red-team depth from adjacent AppSec experience.

## Compensation extraction

If the job record has no explicit `compensation_text`, the evaluator can extract an annual base salary from the raw JD when it finds a clear salary/pay context such as:

```text
The base salary range for this position is $250,000 - $300,000.
```

Numbers such as `2025` and `401k` are ignored.

## Re-analysis semantics

Every analysis reparses the canonical raw JD and replaces the job's parsed requirement rows. Parser improvements therefore apply to already-ingested jobs without creating duplicate job records.
