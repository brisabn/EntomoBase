from helpers import create_project, create_specimen, error_code, project_body


def test_create_project(client, admin):
    response = client.post("/projects", json=project_body(locality="Rio Doce", description="d"), headers=admin)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] and body["title"] == "Project A" and body["locality"] == "Rio Doce" and body["finished"] is True


def test_finished_defaults_to_false(client, admin):
    body = {"title": "T", "year": 2025, "insect_group": "G"}
    assert client.post("/projects", json=body, headers=admin).json()["finished"] is False


def test_validation_problems_are_listed_by_field(client, admin):
    response = client.post("/projects", json={"title": "", "year": 1800}, headers=admin)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_request"
    problems = {(p["field"], p["code"]): p["params"] for p in detail["problems"]}
    assert problems[("title", "empty")] == {}
    assert problems[("year", "min")] == {"limit": 1900}
    assert ("insect_group", "required") in problems


def test_year_above_the_limit_is_refused(client, admin):
    response = client.post("/projects", json=project_body(year=2200), headers=admin)
    problem = response.json()["detail"]["problems"][0]
    assert (problem["field"], problem["code"], problem["params"]) == ("year", "max", {"limit": 2100})


def test_list_is_ordered_by_year_then_id(client, admin):
    create_project(client, admin, title="Old", year=2020)
    create_project(client, admin, title="New A", year=2026)
    create_project(client, admin, title="New B", year=2026)
    assert [p["title"] for p in client.get("/projects").json()] == ["New A", "New B", "Old"]


def test_list_filters(client, admin):
    create_project(client, admin, title="A", year=2024, insect_group="Coleoptera", locality="Rio Doce")
    create_project(client, admin, title="B", year=2025, insect_group="Lepidoptera", locality="Cipó")
    titles = lambda q: [p["title"] for p in client.get(f"/projects?{q}").json()]
    assert titles("year=2024") == ["A"]
    assert titles("insect_group=lepi") == ["B"]
    assert titles("locality=RIO") == ["A"]
    assert titles("year=2024&insect_group=lepi") == []


def test_update_changes_only_the_fields_sent(client, admin):
    project = create_project(client, admin, description="keep me")
    response = client.put(f"/projects/{project['id']}", json={"title": "New title", "finished": False}, headers=admin)
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "New title" and body["finished"] is False and body["description"] == "keep me"


def test_update_can_clear_an_optional_field(client, admin):
    project = create_project(client, admin, description="to remove")
    body = client.put(f"/projects/{project['id']}", json={"description": None}, headers=admin).json()
    assert body["description"] is None


def test_update_missing_project(client, admin):
    response = client.put("/projects/999", json={"title": "x"}, headers=admin)
    assert response.status_code == 404 and error_code(response) == "project_not_found"


def test_delete_project_deletes_its_specimens(client, admin):
    project = create_project(client, admin)
    create_specimen(client, admin, "IN-1", project_id=project["id"])
    create_specimen(client, admin, "OUT-1")
    assert client.delete(f"/projects/{project['id']}", headers=admin).status_code == 204
    assert {s["catalog_number"] for s in client.get("/specimens", headers=admin).json()} == {"OUT-1"}
    assert client.get("/projects").json() == []


def test_delete_missing_project(client, admin):
    response = client.delete("/projects/999", headers=admin)
    assert response.status_code == 404 and error_code(response) == "project_not_found"
