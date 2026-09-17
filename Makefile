.PHONY: test lint run validate-kb seed-kb seed-kb-dry-run search-evidence verify-phase2 verify-phase3 create-policy ingest-job analyze-job

test:
	pytest

lint:
	ruff check src tests scripts

run:
	uvicorn job_agent.api.main:app --reload --app-dir src

validate-kb:
	PYTHONPATH=src python scripts/validate_knowledge_base.py

seed-kb:
	PYTHONPATH=src python scripts/import_knowledge_base.py

seed-kb-dry-run:
	PYTHONPATH=src python scripts/import_knowledge_base.py --dry-run

search-evidence:
	PYTHONPATH=src python scripts/search_evidence.py --skill "Application Security" --limit 10

verify-phase2:
	PYTHONPATH=src python scripts/verify_phase2.py

verify-phase3:
	PYTHONPATH=src python scripts/verify_phase3.py

create-policy:
	PYTHONPATH=src python scripts/create_targeting_policy.py data/examples/targeting_policy.example.json

# Usage: make ingest-job JD=/path/to/jd.txt COMPANY='Acme' TITLE='Principal AppSec Engineer'
ingest-job:
	PYTHONPATH=src python scripts/ingest_job.py "$(JD)" --company "$(COMPANY)" --title "$(TITLE)"

# Usage: make analyze-job JOB_ID=<uuid>
analyze-job:
	PYTHONPATH=src python scripts/analyze_job.py "$(JOB_ID)"
