from helpers import create_project, create_specimen, error_code, specimen_body


def test_create_specimen_with_measurements(client, admin):
    body = specimen_body("A-1", family="Scarabaeidae", latitude=-19.5, longitude=-43.5, collection_date="2025-03-14",
                         measurements=[{"trait": "Comprimento corporal", "value": 60.5}, {"trait": "Chifre", "value": 12, "unit": "cm"}])
    response = client.post("/specimens", json=body, headers=admin)
    assert response.status_code == 201
    created = response.json()
    assert created["collection_date"] == "2025-03-14"
    assert [(m["trait"], m["value"], m["unit"]) for m in created["measurements"]] == [
        ("Comprimento corporal", 60.5, "mm"), ("Chifre", 12.0, "cm")]


def test_duplicate_catalog_number_is_refused(client, admin):
    create_specimen(client, admin, "DUP-1")
    response = client.post("/specimens", json=specimen_body("DUP-1"), headers=admin)
    assert response.status_code == 400 and error_code(response) == "duplicate_catalog_number"


def test_validation_problems(client, admin):
    body = specimen_body("V-1", latitude=99, longitude=-200, measurements=[{"trait": "x", "value": -1}])
    response = client.post("/specimens", json=body, headers=admin)
    assert response.status_code == 422
    problems = {(p["field"], p["code"]): p["params"] for p in response.json()["detail"]["problems"]}
    assert problems[("latitude", "max")] == {"limit": 90}
    assert problems[("longitude", "min")] == {"limit": -180}
    assert problems[("measurements.0.value", "min")] == {"limit": 0}


def test_required_fields(client, admin):
    response = client.post("/specimens", json={}, headers=admin)
    fields = {p["field"] for p in response.json()["detail"]["problems"] if p["code"] == "required"}
    assert fields == {"catalog_number", "insect_order", "species"}


def test_invalid_date_is_an_invalid_value(client, admin):
    response = client.post("/specimens", json=specimen_body("D-1", collection_date="not a date"), headers=admin)
    problem = response.json()["detail"]["problems"][0]
    assert (problem["field"], problem["code"]) == ("collection_date", "invalid_value")


def test_list_is_ordered_and_includes_measurements(client, admin):
    create_specimen(client, admin, "B-2", insect_order="Lepidoptera", species="Morpho helenor")
    create_specimen(client, admin, "A-1", insect_order="Coleoptera", species="Zeta alpha",
                    measurements=[{"trait": "t", "value": 1}])
    create_specimen(client, admin, "A-2", insect_order="Coleoptera", species="Alpha beta")
    listed = client.get("/specimens", headers=admin).json()
    assert [s["catalog_number"] for s in listed] == ["A-2", "A-1", "B-2"]
    assert listed[1]["measurements"][0]["trait"] == "t"


def test_list_filters(client, admin):
    project = create_project(client, admin)
    create_specimen(client, admin, "H-1", species="Dynastes hercules", project_id=project["id"])
    create_specimen(client, admin, "H-2", species="Dynastes tityus")
    create_specimen(client, admin, "M-1", species="Morpho helenor", project_id=project["id"])
    codes = lambda q: {s["catalog_number"] for s in client.get(f"/specimens?{q}", headers=admin).json()}
    assert codes("species=dynastes") == {"H-1", "H-2"}
    assert codes(f"project_id={project['id']}") == {"H-1", "M-1"}
    assert codes(f"species=dynastes&project_id={project['id']}") == {"H-1"}


def test_update_fields(client, admin):
    specimen = create_specimen(client, admin, "U-1", family="Old")
    response = client.put(f"/specimens/{specimen['id']}", json={"family": "New", "habitat": "Cerrado"}, headers=admin)
    body = response.json()
    assert response.status_code == 200 and body["family"] == "New" and body["habitat"] == "Cerrado"
    assert body["species"] == "Dynastes hercules"


def test_update_never_empties_the_required_fields(client, admin):
    specimen = create_specimen(client, admin, "U-2")
    body = client.put(f"/specimens/{specimen['id']}", json={"species": None, "catalog_number": None, "insect_order": None}, headers=admin).json()
    assert (body["catalog_number"], body["species"], body["insect_order"]) == ("U-2", "Dynastes hercules", "Coleoptera")


def test_update_can_clear_an_optional_field(client, admin):
    specimen = create_specimen(client, admin, "U-3", family="Scarabaeidae")
    body = client.put(f"/specimens/{specimen['id']}", json={"family": None}, headers=admin).json()
    assert body["family"] is None


def test_measurements_are_replaced_when_sent_and_kept_when_not(client, admin):
    specimen = create_specimen(client, admin, "M-1", measurements=[{"trait": "a", "value": 1}, {"trait": "b", "value": 2}])
    url = f"/specimens/{specimen['id']}"
    kept = client.put(url, json={"habitat": "x"}, headers=admin).json()
    assert [m["trait"] for m in kept["measurements"]] == ["a", "b"]
    replaced = client.put(url, json={"measurements": [{"trait": "c", "value": 3}]}, headers=admin).json()
    assert [m["trait"] for m in replaced["measurements"]] == ["c"]
    cleared = client.put(url, json={"measurements": []}, headers=admin).json()
    assert cleared["measurements"] == []


def test_update_to_an_existing_catalog_number_is_refused(client, admin):
    create_specimen(client, admin, "X-1")
    other = create_specimen(client, admin, "X-2")
    response = client.put(f"/specimens/{other['id']}", json={"catalog_number": "X-1"}, headers=admin)
    assert response.status_code == 400 and error_code(response) == "duplicate_catalog_number"


def test_update_keeping_the_same_catalog_number_is_allowed(client, admin):
    specimen = create_specimen(client, admin, "X-3")
    response = client.put(f"/specimens/{specimen['id']}", json={"catalog_number": "X-3", "habitat": "y"}, headers=admin)
    assert response.status_code == 200


def test_update_and_delete_missing_specimen(client, admin):
    for response in (client.put("/specimens/999", json={"habitat": "x"}, headers=admin), client.delete("/specimens/999", headers=admin)):
        assert response.status_code == 404 and error_code(response) == "specimen_not_found"


def test_delete_specimen_removes_its_measurements(client, admin, db):
    import models
    specimen = create_specimen(client, admin, "DEL-1", measurements=[{"trait": "a", "value": 1}])
    assert client.delete(f"/specimens/{specimen['id']}", headers=admin).status_code == 204
    assert client.get("/specimens", headers=admin).json() == []
    assert db.query(models.Measurement).count() == 0


def test_demo_image_is_generated_for_a_known_file(client, admin):
    create_specimen(client, admin, "IMG-1", image_file="IMG-1.svg")
    response = client.get("/demo/image/IMG-1.svg")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert "IMG-1" in response.text
    assert client.get("/demo/image/IMG-1.svg").text == response.text


def test_demo_image_for_an_unknown_file(client):
    response = client.get("/demo/image/nothing.svg")
    assert response.status_code == 404 and error_code(response) == "image_not_found"
