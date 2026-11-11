def preflight(client, origin, method="POST", headers="authorization,content-type"):
    return client.options("/projects", headers={
        "Origin": origin, "Access-Control-Request-Method": method, "Access-Control-Request-Headers": headers,
    })


def test_the_configured_origin_is_allowed(client):
    response = preflight(client, "http://allowed.test")
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://allowed.test"


def test_other_origins_are_refused(client):
    response = preflight(client, "https://evil.example")
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_the_development_origin_is_not_allowed_in_production_settings(client):
    assert "access-control-allow-origin" not in preflight(client, "http://127.0.0.1:5500").headers


def test_only_the_expected_methods_are_allowed(client):
    assert preflight(client, "http://allowed.test", "DELETE").status_code == 200
    assert preflight(client, "http://allowed.test", "PATCH").status_code == 400


def test_only_the_expected_headers_are_allowed(client):
    assert preflight(client, "http://allowed.test", headers="x-custom").status_code == 400


def test_no_credentials_are_allowed(client):
    assert "access-control-allow-credentials" not in preflight(client, "http://allowed.test").headers


def test_a_normal_response_carries_the_origin_header(client):
    response = client.get("/projects", headers={"Origin": "http://allowed.test"})
    assert response.headers["access-control-allow-origin"] == "http://allowed.test"
    assert "access-control-allow-origin" not in client.get("/projects", headers={"Origin": "https://evil.example"}).headers
