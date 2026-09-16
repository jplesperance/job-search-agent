from job_agent.api.main import app


def test_phase2_routes_are_registered():
    routes = {(route.path, ",".join(sorted(route.methods or []))) for route in app.routes}
    assert ("/health", "GET") in routes
    assert ("/api/v1/profile", "GET") in routes
    assert ("/api/v1/experiences", "GET") in routes
    assert ("/api/v1/skills", "GET") in routes
    assert ("/api/v1/certifications", "GET") in routes
    assert ("/api/v1/evidence", "GET") in routes
    assert ("/api/v1/evidence/search", "POST") in routes
    assert ("/api/v1/evidence/{identifier}", "GET") in routes
