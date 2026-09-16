# Phase 1 Data Model

```text
career_profiles
  1 |---* experiences
  1 |---* certifications

experiences
  1 |---* evidence_items

evidence_items
  * |---* skills        (through evidence_skills)

targeting_policies
  1 |---* job_analyses

job_opportunities
  1 |---* job_analyses
  1 |---0..1 applications

applications
  1 |---* application_events
```

## Evidence is the anti-hallucination boundary

An `evidence_item` is a resume-safe atomic fact or accomplishment. An item starts as `draft` and becomes usable by downstream resume generation only after it is `approved`.

Examples of evidence categories:
- responsibility
- achievement
- leadership
- security_program
- architecture
- incident_response
- compliance
- vulnerability_management
- training

`provenance` records where the fact came from (master resume, user-confirmed statement, performance review, etc.).

## Targeting policy is versioned

Scoring criteria will evolve. Analyses therefore point to the exact policy version that produced them rather than to mutable global settings.

## Application events are append-only

`applications.status` is the current projection for fast reads. `application_events` preserves the history needed to reconstruct who or what changed a status and why.
