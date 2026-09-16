# System Design

## 1. System context

The platform is an orchestrated job-search workflow. Durable domain state is stored in PostgreSQL. Agents are bounded decision/work units that read structured state and return structured outputs. External systems are reached through adapters introduced in later phases.

```text
                        +--------------------+
                        |   Human Operator   |
                        | approval / policy  |
                        +---------+----------+
                                  |
                                  v
+----------------+       +--------+---------+       +-------------------+
| External job   | ----> | Orchestrator/API | ----> | Specialist agents |
| sources        |       +--------+---------+       +-------------------+
+----------------+                |
                                  v
                         +--------+---------+
                         |   PostgreSQL     |
                         | source of truth  |
                         +------------------+
```

## 2. Phase 1 bounded contexts

### Career Knowledge
Stores factual, approved evidence about the candidate:
- employment experiences
- achievements/evidence items
- skills
- certifications
- education (planned extension)
- resume-safe claims and provenance

### Targeting Policy
Stores preferences and constraints:
- target titles
- seniority
- locations / remote policy
- compensation floor
- employment type
- required/excluded technologies or domains
- disqualifiers
- scoring weights

### Opportunity Analysis
Stores jobs manually inserted in Phase 1 and automatically ingested in Phase 2:
- raw description
- normalized requirements
- fit analysis
- hard-filter result
- score components
- evidence supporting each match
- gaps and unknowns

### Application Tracking
Stores lifecycle state:
- application
- current state
- status history
- immutable application events
- artifacts associated with an application (Phase 3+)

## 3. Trust boundaries

1. LLM output is untrusted until validated against a Pydantic contract.
2. Resume claims may only reference approved evidence IDs.
3. Database writes occur through repositories/services, never directly from prompts.
4. External side effects will be separate tools with explicit approval/policy checks.
5. Secrets remain outside prompts and application records.

## 4. Agent model

The future orchestrator uses manager-style orchestration. Specialist agents are invoked as bounded tools and return typed outputs.

Initial future agents:
- DiscoveryAgent (Phase 2)
- JobMatchAgent (Phase 2)
- ResumeAgent (Phase 3)
- ApplicationAgent (Phase 4)
- InboxAgent (Phase 5)

Phase 1 contains only contracts and domain services needed by those agents.

## 5. Data flow for a job analysis

```text
Job record
   |
   +--> Hard filters (deterministic) ---- fail --> rejected_by_policy
   |
   +--> Requirement extraction
   |
   +--> Evidence retrieval
   |
   +--> Semantic analysis / structured output
   |
   +--> Weighted scoring
   |
   +--> Persist analysis + evidence links + gaps
```

## 6. Security requirements

- Use least-privilege DB credentials in non-local environments.
- Encrypt secrets using a secrets manager; never store OAuth tokens in application tables.
- Keep original source text separately from model-generated analysis.
- Record model/tool provenance for generated decisions.
- Treat job descriptions and inbound email as hostile/untrusted content; never allow embedded instructions to alter agent policy.
- Require explicit approval before any external submission until an allowlisted auto-apply policy is intentionally introduced.
