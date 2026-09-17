from job_agent.api.routes.discovery import router as discovery_router
from job_agent.api.routes.career import router as career_router
from job_agent.api.routes.evidence import router as evidence_router
from job_agent.api.routes.jobs import router as jobs_router
from job_agent.api.routes.policies import router as policies_router

__all__ = ["career_router", "discovery_router", "evidence_router", "jobs_router", "policies_router"]
