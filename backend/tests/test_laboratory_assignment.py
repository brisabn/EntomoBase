import pytest

import models
from helpers import create_project, create_specimen, error_code, specimen_body
from laboratories import DEFAULT_LABORATORY, default_laboratory


@pytest.fixture
def two_labs(db):
    # the first laboratory is created on demand by the API; the second one is added directly
    first = default_laboratory(db)
    second = models.Laboratory(slug="b", name="Lab B", institution="B", collection_code="B", license="x", listed=True)
    db.add(second)
    db.commit()
    return first.id, second.id


# a specimen that belongs to the other laboratory, created behind the API's back
def specimen_of(db, laboratory_id, code, **extra):
    row = models.Specimen(laboratory_id=laboratory_id, catalog_number=code, insect_order="Coleoptera", species="Dynastes hercules", **extra)
    db.add(row)
    db.commit()
    return row


# ---------- the default laboratory ----------
def test_the_default_laboratory_is_created_when_there_is_none(db):
    assert db.query(models.Laboratory).count() == 0
    lab = default_laboratory(db)
    assert (lab.slug, lab.name, lab.institution, lab.listed) == (DEFAULT_LABORATORY["slug"], "EntomoBase UFMG", "UFMG", True)


def test_the_default_laboratory_is_always_the_first_one(db, two_labs):
    first, _ = two_labs
    assert default_laboratory(db).id == first
    assert db.query(models.Laboratory).count() == 2


# ---------- projects ----------
def test_a_new_project_goes_to_the_laboratory_of_the_request(client, admin, db):
    create_project(client, admin, title="A")
    create_project(client, admin, title="B")
    assert {p.laboratory_id for p in db.query(models.Project).all()} == {default_laboratory(db).id}


def test_a_new_project_is_private_unless_told_otherwise(client, admin, db):
    body = {"title": "T", "year": 2025, "insect_group": "G", "finished": True}
    assert client.post("/projects", json=body, headers=admin).json()["visibility"] == "private"


def test_finishing_a_project_does_not_publish_it(client, admin):
    project = create_project(client, admin, finished=False, visibility="private")
    body = client.put(f"/projects/{project['id']}", json={"finished": True}, headers=admin).json()
    assert body["finished"] is True and body["visibility"] == "private"


# ---------- specimens ----------
def test_a_specimen_belongs_to_the_laboratory_of_the_request(client, admin, db):
    project = create_project(client, admin)
    with_project = create_specimen(client, admin, "S-1", project_id=project["id"])
    without_project = create_specimen(client, admin, "S-2")
    lab = default_laboratory(db).id
    assert db.get(models.Specimen, with_project["id"]).laboratory_id == lab
    assert db.get(models.Specimen, without_project["id"]).laboratory_id == lab


def test_the_same_catalog_number_can_exist_in_two_laboratories(client, admin, db, two_labs):
    _, second = two_labs
    specimen_of(db, second, "SAME-1")
    response = client.post("/specimens", json=specimen_body("SAME-1"), headers=admin)
    assert response.status_code == 201


def test_the_same_catalog_number_is_refused_inside_a_laboratory(client, admin, two_labs):
    create_specimen(client, admin, "SAME-1")
    response = client.post("/specimens", json=specimen_body("SAME-1"), headers=admin)
    assert response.status_code == 400 and error_code(response) == "duplicate_catalog_number"


def test_renaming_to_a_number_used_in_the_same_laboratory_is_refused(client, admin):
    create_specimen(client, admin, "TAKEN-1")
    other = create_specimen(client, admin, "OTHER-1")
    response = client.put(f"/specimens/{other['id']}", json={"catalog_number": "TAKEN-1"}, headers=admin)
    assert response.status_code == 400 and error_code(response) == "duplicate_catalog_number"


def test_renaming_to_a_number_used_only_in_another_laboratory_is_allowed(client, admin, db, two_labs):
    _, second = two_labs
    specimen_of(db, second, "ELSEWHERE-1")
    mine = create_specimen(client, admin, "MINE-1")
    response = client.put(f"/specimens/{mine['id']}", json={"catalog_number": "ELSEWHERE-1"}, headers=admin)
    assert response.status_code == 200


def test_keeping_the_same_number_on_update_is_not_a_duplicate(client, admin):
    specimen = create_specimen(client, admin, "KEEP-1")
    response = client.put(f"/specimens/{specimen['id']}", json={"catalog_number": "KEEP-1", "habitat": "x"}, headers=admin)
    assert response.status_code == 200


# ---------- bulk import ----------
def import_rows(client, admin, rows, **payload):
    return client.post("/specimens/import?validate_names=false", json={"rows": rows, **payload}, headers=admin)


def row(code, **extra):
    return {"catalog_number": code, "insect_order": "Coleoptera", "species": "Dynastes hercules", **extra}


def test_imported_specimens_go_to_the_laboratory_of_the_request(client, admin, db):
    project = create_project(client, admin)
    import_rows(client, admin, [row("IMP-1"), row("IMP-2")], project_id=project["id"])
    assert {s.laboratory_id for s in db.query(models.Specimen).all()} == {default_laboratory(db).id}


def test_a_number_that_exists_only_in_another_laboratory_is_a_new_specimen_when_importing(client, admin, db, two_labs):
    first, second = two_labs
    other = specimen_of(db, second, "SAME-1", habitat="kept")
    report = import_rows(client, admin, [row("SAME-1", habitat="changed")], duplicates="update").json()
    assert (report["created"], report["updated"], report["skipped"]) == (1, 0, 0)
    db.expire_all()
    assert db.get(models.Specimen, other.id).habitat == "kept"
    assert db.query(models.Specimen).filter_by(laboratory_id=first, catalog_number="SAME-1").one().habitat == "changed"


def test_a_number_that_exists_in_the_same_laboratory_is_still_a_duplicate_when_importing(client, admin, two_labs):
    project = create_project(client, admin)
    create_specimen(client, admin, "SAME-1", project_id=project["id"])
    report = import_rows(client, admin, [row("SAME-1")], project_id=project["id"]).json()
    assert (report["created"], report["skipped"]) == (0, 1)


def test_the_same_number_twice_in_one_file_is_still_an_error(client, admin):
    response = client.post("/specimens/import?dry_run=true&validate_names=false", json={"rows": [row("TWICE-1"), row("TWICE-1")]}, headers=admin)
    report = response.json()
    assert report["errors"][0]["problems"][0]["code"] == "duplicate_in_file"
