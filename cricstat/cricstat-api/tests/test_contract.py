"""F5 contract: envelope, caching, problem+json errors, GET-only, schema served."""
from tests.conftest import pid

KOHLI = pid("V Kohli")


def test_health(client):
    r = client.get("/v1/health")
    assert r.status_code == 200 and r.json()["status"] == "ok" and r.json()["build_id"] == 1


def test_envelope_carries_provenance(client):
    r = client.get("/v1/players/%s/career?scope=ODI" % KOHLI)
    assert r.status_code == 200
    meta = r.json()["meta"]
    assert meta["build_id"] == 1 and meta["data_as_of"] == "2025-01-10"
    assert meta["filters"] == {"scope": "ODI"}
    assert "Open Data Commons Attribution License 1.0" in meta["attribution"]
    assert "Afghanistan" in meta["coverage"]
    assert "dismissals" in meta["metrics"]["average"]          # from semantic_catalog


def test_etag_and_cache_headers(client):
    r = client.get("/v1/meta/scopes")
    assert r.headers["etag"] == '"1"'
    assert r.headers["cache-control"] == "public, max-age=300, stale-while-revalidate=3600"
    again = client.get("/v1/meta/scopes", headers={"If-None-Match": '"1"'})
    assert again.status_code == 304 and again.content == b""


def _problem(r, status):
    assert r.status_code == status
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["status"] == status and body["title"] and body["detail"]
    return body


def test_errors_are_problem_json(client):
    _problem(client.get("/v1/players/ffffffff"), 404)
    _problem(client.get("/v1/teams/nowhere-men"), 404)
    assert "unknown scope" in _problem(client.get("/v1/players/%s/career?scope=XYZ" % KOHLI),
                                       400)["detail"]
    _problem(client.get("/v1/players/%s/phases?scope=TEST" % KOHLI), 422)
    _problem(client.get("/v1/players/%s/innings?from=yesterday" % KOHLI), 400)
    _problem(client.get("/v1/players/%s/innings?limit=101" % KOHLI), 400)
    _problem(client.get("/v1/players/%s/innings?limit=abc" % KOHLI), 400)
    _problem(client.get("/v1/search?q=x"), 400)
    _problem(client.get("/v1/no-such-endpoint"), 404)


def test_get_only(client):
    assert client.post("/v1/players/%s" % KOHLI).status_code == 405
    assert client.delete("/v1/teams/india-men").status_code == 405


def test_openapi_served_without_cdn_pages(client):
    assert client.get("/openapi.json").json()["info"]["title"] == "cricstat API"
    assert client.get("/docs").status_code == 404


def test_no_db_gives_503(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from presentation_logic.api.app import create_app
    from shared.config import Config

    monkeypatch.setenv("CRICSTAT_HOME", str(tmp_path))
    with TestClient(create_app(Config())) as c:
        assert c.get("/v1/health").status_code == 503
        _problem(c.get("/v1/meta/scopes"), 503)
