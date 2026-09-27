# Phase 4.1 ORM duplicate-definition hotfix

This hotfix replaces only `src/job_agent/db/tables.py` with the clean Phase 4.1 model file.

It fixes SQLAlchemy import failures such as:

- `Table 'job_source_postings' is already defined for this MetaData instance`
- the follow-on `Table 'career_profiles' is already defined...` error after a partial failed import

## Apply

From the repository root:

```bash
unzip -o /path/to/job-agent-phase4.1-orm-duplicate-hotfix-v0.4.4.1.zip -d .
find src -type d -name __pycache__ -prune -exec rm -rf {} +
PYTHONPATH=src pytest -q
```

Expected result against the Phase 4.1 tree:

```text
56 passed
```

No Alembic migration is added or changed by this hotfix.
