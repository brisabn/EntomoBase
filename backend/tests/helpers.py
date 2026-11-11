def project_body(**overrides):
    body = {"title": "Project A", "year": 2025, "insect_group": "Coleoptera", "finished": True}
    body.update(overrides)
    return body


def specimen_body(code="S-1", **overrides):
    body = {"catalog_number": code, "insect_order": "Coleoptera", "species": "Dynastes hercules"}
    body.update(overrides)
    return body


def error_code(response):
    return response.json()["detail"]["code"]


def create_project(client, admin, **overrides):
    response = client.post("/projects", json=project_body(**overrides), headers=admin)
    assert response.status_code == 201, response.text
    return response.json()


def create_specimen(client, admin, code="S-1", **overrides):
    response = client.post("/specimens", json=specimen_body(code, **overrides), headers=admin)
    assert response.status_code == 201, response.text
    return response.json()
