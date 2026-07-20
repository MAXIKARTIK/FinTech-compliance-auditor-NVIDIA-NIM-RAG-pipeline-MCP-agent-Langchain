def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["api"] == "ok"
    assert {"postgres", "redis", "chroma"} <= set(r.json().keys())
