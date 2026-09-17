from job_agent.api.main import app


def test_phase3_routes_are_registered():
    routes = {(route.path, ",".join(sorted(route.methods or []))) for route in app.routes}
    assert ("/health", "GET") in routes
    assert ("/api/v1/profile", "GET") in routes
    assert ("/api/v1/experiences", "GET") in routes
    assert ("/api/v1/skills", "GET") in routes
    assert ("/api/v1/certifications", "GET") in routes
    assert ("/api/v1/evidence", "GET") in routes
    assert ("/api/v1/evidence/search", "POST") in routes
    assert ("/api/v1/evidence/{identifier}", "GET") in routes
    assert ("/api/v1/discovery/sources", "GET") in routes
    assert ("/api/v1/discovery/sources", "POST") in routes
    assert ("/api/v1/discovery/run", "POST") in routes
    assert ("/api/v1/discovery/runs", "GET") in routes
    assert ("/api/v1/discovery/candidates", "GET") in routes
    assert ("/api/v1/targeting-policies", "GET") in routes
    assert ("/api/v1/targeting-policies", "POST") in routes
    assert ("/api/v1/targeting-policies/activate", "POST") in routes
    assert ("/api/v1/jobs/ingest", "POST") in routes
    assert ("/api/v1/jobs", "GET") in routes
    assert ("/api/v1/jobs/{job_id}", "GET") in routes
    assert ("/api/v1/jobs/{job_id}/requirements", "GET") in routes
    assert ("/api/v1/jobs/{job_id}/analyze", "POST") in routes
    assert ("/api/v1/jobs/{job_id}/analyses/latest", "GET") in routes
