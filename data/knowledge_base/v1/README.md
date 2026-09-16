# Knowledge Base v1

Primary artifact: `knowledge_base.json`.

Normalized entity files are provided to make ingestion, diffing, and review easier. `postgres_compat_seed.json` maps the richer v1 dataset into the current Phase-1 SQLAlchemy schema; technologies and frameworks are represented as skill rows in that compatibility view because the current database schema does not yet have separate technology/framework tables.

## Verification statuses
- `USER_VERIFIED`: explicitly confirmed in the role-by-role interview.
- `SOURCE_FACT`: present in an uploaded resume but not separately confirmed in the interview.
- `CORROBORATED`: consistent across multiple source documents.
- `NEEDS_VERIFICATION`: intentionally unresolved; agent must not state as fact.

## Resume visibility
- `public_safe`: may be considered for resume use.
- `generalize`: use the underlying capability/impact but avoid unnecessary internal names/details.
- `internal_only`: usable for matching/context, but should not be placed into a public resume by default.

The `corrections_and_agent_constraints.json` file contains hard rules that downstream agents must honor.

## PostgreSQL import

The current Phase-1 schema can ingest the compatibility view with:

```bash
PYTHONPATH=src python scripts/import_knowledge_base.py --dry-run
PYTHONPATH=src python scripts/import_knowledge_base.py
```

The richer JSON remains authoritative because the current database schema intentionally collapses technologies and frameworks into the `skills` table. A later migration can normalize those into dedicated tables without losing information from `knowledge_base.json`.
