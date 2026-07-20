def test_rule_crud_lifecycle(client, auth_headers):
    payload = {
        "rule_id": "SOX-302",
        "title": "CEO/CFO Certification",
        "regulation": "SOX",
        "description": "Officers must certify financial reports.",
        "check_prompt": "Does the filing include CEO and CFO certifications?",
        "severity_weight": 9,
    }
    r = client.post("/rules", json=payload, headers=auth_headers)
    assert r.status_code == 201, r.text
    assert r.json()["version"] == 1

    assert any(x["rule_id"] == "SOX-302" for x in client.get("/rules").json())
    assert client.get("/rules/SOX-302").json()["severity_weight"] == 9

    upd = {**payload, "severity_weight": 7}
    del upd["rule_id"]
    r = client.put("/rules/SOX-302", json=upd, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["version"] == 2
    assert r.json()["severity_weight"] == 7

    assert client.delete("/rules/SOX-302", headers=auth_headers).status_code == 204
    assert client.get("/rules/SOX-302").status_code == 404


def test_rule_requires_auth(client):
    assert client.post("/rules", json={}).status_code == 401


def test_rule_validation_error(client, auth_headers):
    bad = {
        "rule_id": "X",
        "title": "t",
        "regulation": "SOX",
        "check_prompt": "c",
        "severity_weight": 99,
    }
    assert client.post("/rules", json=bad, headers=auth_headers).status_code == 422
