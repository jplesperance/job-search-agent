from job_agent.api.main import app


_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}


def _openapi_routes() -> set[tuple[str, str]]:
    """Return documented API routes without depending on FastAPI router internals.

    FastAPI 0.137+ may keep include_router() entries as _IncludedRouter objects,
    which intentionally do not expose .path/.methods like APIRoute did when
    included routers were flattened. OpenAPI is the stable public contract we
    actually want this test to verify.
    """
    schema = app.openapi()
    return {
        (path, method.upper())
        for path, path_item in schema.get("paths", {}).items()
        for method in path_item
        if method.lower() in _HTTP_METHODS
    }


def test_phase3_routes_are_registered():
    routes = _openapi_routes()
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
