# Phase 1 Build Plan

## Goal

Create a trustworthy system of record that can answer:

1. What career facts are we allowed to claim?
2. What kind of role are we targeting?
3. Does a given job pass hard constraints?
4. How strongly does the job match, and why?
5. What is the lifecycle state of each opportunity/application?

## Milestones

### P1.1 — Bootstrap
- repository scaffold
- configuration
- PostgreSQL + pgvector local service
- SQLAlchemy base/session
- Alembic
- test harness

### P1.2 — Career knowledge base
- profile
- experience
- evidence item
- skill taxonomy
- evidence-to-skill mapping
- certification
- provenance / approval status

Acceptance criterion: every resume-safe claim can be traced to an approved evidence item.

### P1.3 — Targeting policy
- hard constraints
- preferences
- weighted criteria
- versioned scoring profile

Acceptance criterion: the same inputs produce the same deterministic hard-filter result.

### P1.4 — Opportunity + scoring
- job entity
- normalized job requirements
- job analysis contract
- score component persistence
- evidence links and gap list

Acceptance criterion: analysis output is typed, explainable, and references existing evidence IDs.

### P1.5 — Application state machine
- application entity
- legal transitions
- immutable event log
- transition tests

Acceptance criterion: invalid transitions are rejected and every valid transition emits an event.

## Out of scope

- LinkedIn scraping/browser login
- ATS automation
- Gmail monitoring
- resume generation
- application form filling/submission
- calendar scheduling
