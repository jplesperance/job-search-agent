from fastapi import FastAPI

from job_agent.api.routes import career_router, evidence_router, jobs_router, policies_router

app = FastAPI(title="Job Agent System", version="0.3.0")
app.include_router(career_router, prefix="/api/v1")
app.include_router(evidence_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(policies_router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.3.0"}
