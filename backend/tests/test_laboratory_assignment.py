import pytest

import models
from helpers import create_project, create_specimen, error_code, specimen_body
from laboratories import DEFAULT_LABORATORY, default_laboratory, laboratory_id_for_project, visibility_from_status


@pytest.fixture
def two_labs(db):
    # the first laboratory is created on demand by the API; the second one is added directly
    first = default_laboratory(db)
    second = models.Laboratory(slug="b", name="Lab B", institution="B", collection_code="B", license="x", listed=True)
    db.add(second)
    db.commit()
    return first.id, second.id


def put_project_in(db, project_id, laboratory_id):
    db.query(models.Project).filter_by(id=project_id).update({"laboratory_id": laboratory_id})
    db.commit()


# ---------- helpers ----------
def test_the_default_laboratory_is_created_when_there_is_none(db):
    assert db.query(models.Laboratory).count() == 0
    lab = default_laboratory(db)
    assert (lab.slug, lab.name, lab.institution, lab.listed) == (DEFAULT_LABORATORY["slug"], "EntomoBase UFMG", "UFMG", True)


def test_the_default_laboratory_is_always_the_first_one(db, two_labs):
    first, _ = two_labs
    assert default_laboratory(db).id == first
    assert db.query(models.Laboratory).count() == 2


def test_visibility_follows_the_status():
    assert visibility_from_status(True) == "public"
    assert visibility_from_status(False) == "private"
    assert visibility_from_status(None) == "private"


def test_a_specimen_without_a_project_goes_to_the_default_laboratory(db, two_labs):
    assert laboratory_id_for_project(db, None) == two_labs[0]
    assert laboratory_id_for_project(db, 999) == two_labs[0]


# ---------- projects ----------
def test_a_new_project_goes_to_the_laboratory_and_follows_its_status(client, admin, db):
    finished = create_project(client, admin, title="Done", finished=True)
    running = create_project(client, admin, title="Running", finished=False)
    rows = {p.title: p for p in db.query(models.Project).all()}
    assert rows["Done"].visibility == "public" and rows["Running"].visibility == "private"
    assert {p.laboratory_id for p in rows.values()} == {default_laboratory(db).id}
    assert finished["id"] != running["id"]


def test_changing_the_status_changes_the_visibility(client, admin, db):
    project = create_project(client, admin, finished=False)
    client.put(f"/projects/{project['id']}", json={"finished": True}, headers=admin)
    db.expire_all()
    assert db.get(models.Project, project["id"]).visibility == "public"
    client.put(f"/projects/{project['id']}", json={"finished": False}, headers=admin)
    db.expire_all()
    assert db.get(models.Project, project["id"]).visibility == "private"


def test_editing_something_else_leaves_the_visibility_alone(client, admin, db):
    project = create_project(client, admin, finished=True)
    db.query(models.Project).filter_by(id=project["id"]).update({"visibility": "unlisted"})
    db.commit()
    client.put(f"/projects/{project['id']}", json={"title": "New title"}, headers=admin)
    db.expire_all()
    assert db.get(models.Project, project["id"]).visibility == "unlisted"


def test_the_laboratory_is_not_part_of_the_api_response(client, admin):
    project = create_project(client, admin)
    assert "laboratory_id" not in project and "visibility" not in project and "share_token" not in project


# ---------- specimens ----------
def test_a_specimen_belongs_to_the_laboratory_of_its_project(client, admin, db, two_labs):
    _, second = two_labs
    project = create_project(client, admin)
    put_project_in(db, project["id"], second)
    specimen = create_specimen(client, admin, "S-1", project_id=project["id"])
    assert db.get(models.Specimen, specimen["id"]).laboratory_id == second


def test_a_specimen_without_a_project_belongs_to_the_default_laboratory(client, admin, db, two_labs):
    specimen = create_specimen(client, admin, "S-1")
    assert db.get(models.Specimen, specimen["id"]).laboratory_id == two_labs[0]


def test_the_same_catalog_number_can_exist_in_two_laboratories(client, admin, db, two_labs):
    first, second = two_labs
    project_a = create_project(client, admin, title="A")
    project_b = create_project(client, admin, title="B")
    put_project_in(db, project_b["id"], second)
    create_specimen(client, admin, "SAME-1", project_id=project_a["id"])
    other = client.post("/specimens", json=specimen_body("SAME-1", project_id=project_b["id"]), headers=admin)
    assert other.status_code == 201


def test_the_same_catalog_number_is_refused_inside_a_laboratory(client, admin, db, two_labs):
    project_a = create_project(client, admin, title="A")
    other_project_a = create_project(client, admin, title="A2")
    create_specimen(client, admin, "SAME-1", project_id=project_a["id"])
    response = client.post("/specimens", json=specimen_body("SAME-1", project_id=other_project_a["id"]), headers=admin)
    assert response.status_code == 400 and error_code(response) == "duplicate_catalog_number"


def test_moving_a_specimen_to_a_project_of_another_laboratory_moves_the_specimen(client, admin, db, two_labs):
    _, second = two_labs
    project_a = create_project(client, admin, title="A")
    project_b = create_project(client, admin, title="B")
    put_project_in(db, project_b["id"], second)
    specimen = create_specimen(client, admin, "MOVE-1", project_id=project_a["id"])
    response = client.put(f"/specimens/{specimen['id']}", json={"project_id": project_b["id"]}, headers=admin)
    assert response.status_code == 200
    db.expire_all()
    assert db.get(models.Specimen, specimen["id"]).laboratory_id == second


def test_moving_is_refused_when_the_other_laboratory_already_has_that_number(client, admin, db, two_labs):
    _, second = two_labs
    project_a = create_project(client, admin, title="A")
    project_b = create_project(client, admin, title="B")
    put_project_in(db, project_b["id"], second)
    create_specimen(client, admin, "CLASH-1", project_id=project_b["id"])
    specimen = create_specimen(client, admin, "CLASH-1x", project_id=project_a["id"])
    client.put(f"/specimens/{specimen['id']}", json={"catalog_number": "CLASH-1"}, headers=admin)  # same lab as A: free
    response = client.put(f"/specimens/{specimen['id']}", json={"project_id": project_b["id"]}, headers=admin)
    assert response.status_code == 400 and error_code(response) == "duplicate_catalog_number"


def test_renaming_to_a_number_used_in_the_same_laboratory_is_refused(client, admin):
    create_specimen(client, admin, "TAKEN-1")
    other = create_specimen(client, admin, "OTHER-1")
    response = client.put(f"/specimens/{other['id']}", json={"catalog_number": "TAKEN-1"}, headers=admin)
    assert response.status_code == 400 and error_code(response) == "duplicate_catalog_number"


# ---------- bulk import ----------
def import_rows(client, admin, rows, **payload):
    return client.post("/specimens/import?validate_names=false", json={"rows": rows, **payload}, headers=admin)


def row(code, **extra):
    return {"catalog_number": code, "insect_order": "Coleoptera", "species": "Dynastes hercules", **extra}


def test_imported_specimens_go_to_the_laboratory_of_the_project(client, admin, db, two_labs):
    _, second = two_labs
    project = create_project(client, admin)
    put_project_in(db, project["id"], second)
    import_rows(client, admin, [row("IMP-1")], project_id=project["id"])
    assert db.query(models.Specimen).filter_by(catalog_number="IMP-1").one().laboratory_id == second


def test_a_number_that_exists_only_in_another_laboratory_is_a_new_specimen_when_importing(client, admin, db, two_labs):
    _, second = two_labs
    project_a = create_project(client, admin, title="A")
    project_b = create_project(client, admin, title="B")
    put_project_in(db, project_b["id"], second)
    create_specimen(client, admin, "SAME-1", project_id=project_a["id"], habitat="kept")
    report = import_rows(client, admin, [row("SAME-1", habitat="changed")], project_id=project_b["id"], duplicates="update").json()
    assert (report["created"], report["updated"], report["skipped"]) == (1, 0, 0)
    habitats = {s.laboratory_id: s.habitat for s in db.query(models.Specimen).all()}
    assert habitats[two_labs[0]] == "kept" and habitats[second] == "changed"


def test_a_number_that_exists_in_the_same_laboratory_is_still_a_duplicate_when_importing(client, admin, two_labs):
    project = create_project(client, admin)
    create_specimen(client, admin, "SAME-1", project_id=project["id"])
    report = import_rows(client, admin, [row("SAME-1")], project_id=project["id"]).json()
    assert (report["created"], report["skipped"]) == (0, 1)


def test_the_same_number_twice_in_one_file_is_still_an_error(client, admin):
    response = client.post("/specimens/import?dry_run=true&validate_names=false", json={"rows": [row("TWICE-1"), row("TWICE-1")]}, headers=admin)
    report = response.json()
    assert report["errors"][0]["problems"][0]["code"] == "duplicate_in_file"
