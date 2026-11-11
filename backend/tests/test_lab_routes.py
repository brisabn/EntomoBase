import csv
import io
import zipfile

import pytest

import authorization
import models
from conftest import make_token
from helpers import create_project, create_specimen, error_code, project_body, specimen_body
from laboratories import default_laboratory


# the first laboratory ("ufmg", with the admin of the tests) and a second one ("lab-b") that has a public
# and a private project; the admin of the first one is not a member of the second
@pytest.fixture
def labs(db, user):
    first = default_laboratory(db)
    second = models.Laboratory(slug="lab-b", name="Lab B", institution="BBB", collection_code="COL-B", license="http://b.test", listed=True)
    db.add(second)
    db.flush()
    projects = {}
    for visibility in ("public", "private"):
        project = models.Project(laboratory_id=second.id, title=f"B {visibility}", year=2025, insect_group="Coleoptera", visibility=visibility)
        db.add(project)
        db.flush()
        db.add(models.Specimen(
            laboratory_id=second.id, catalog_number=f"B-{visibility}", insect_order="Coleoptera", species="Dynastes hercules",
            project_id=project.id, collector="B secret",
        ))
        projects[visibility] = project.id
    db.commit()
    return {"first": first, "second": second, "projects": projects}


def member_of_second(db, password_hash, labs, role="researcher", email="b@lab.br"):
    from conftest import add_user
    add_user(email, password_hash)
    user = db.query(models.User).filter_by(email=email).one()
    db.add(models.Membership(user_id=user.id, laboratory_id=labs["second"].id, role=role))
    db.commit()
    return {"Authorization": f"Bearer {make_token(email=email)}"}


# ---------- the laboratory comes from the address ----------
def test_the_same_data_is_in_the_old_and_the_new_address_of_the_first_laboratory(client, admin, labs):
    create_project(client, admin, title="Mine")
    old = client.get("/projects", headers=admin).json()
    new = client.get("/labs/ufmg/projects", headers=admin).json()
    assert old == new and [p["title"] for p in new] == ["Mine"]


def test_each_laboratory_shows_only_its_own_projects(client, labs):
    assert [p["title"] for p in client.get("/labs/lab-b/projects").json()] == ["B public"]
    assert client.get("/labs/ufmg/projects").json() == []


def test_each_laboratory_shows_only_its_own_specimens(client, admin, labs):
    project = create_project(client, admin, title="Mine")
    create_specimen(client, admin, "MINE-1", project_id=project["id"])
    assert {s["catalog_number"] for s in client.get("/labs/ufmg/specimens").json()} == {"MINE-1"}
    assert {s["catalog_number"] for s in client.get("/labs/lab-b/specimens").json()} == {"B-public"}


def test_an_unknown_laboratory_is_a_404(client, admin):
    for method, path in (("get", "/labs/nope/projects"), ("get", "/labs/nope/specimens"), ("get", "/labs/nope/export/csv"),
                         ("get", "/labs/nope/export/dwc"), ("get", "/labs/nope/demo/image/x.svg")):
        response = getattr(client, method)(path, headers=admin)
        assert response.status_code == 404 and error_code(response) == "lab_not_found", path
    response = client.post("/labs/nope/projects", json=project_body(), headers=admin)
    assert response.status_code == 404 and error_code(response) == "lab_not_found"


def test_the_slug_has_to_match_exactly(client, labs):
    assert client.get("/labs/LAB-B/projects").status_code == 404
    assert client.get("/labs/lab-b /projects").status_code == 404


def test_a_slug_in_the_query_of_an_old_address_changes_nothing(client, admin, labs):
    create_project(client, admin, title="Mine")
    assert [p["title"] for p in client.get("/projects?slug=lab-b", headers=admin).json()] == ["Mine"]


# ---------- membership is per laboratory ----------
def test_a_member_of_one_laboratory_is_only_a_visitor_in_another(client, admin, labs):
    assert client.post("/labs/lab-b/projects", json=project_body(), headers=admin).status_code == 403
    assert client.get("/labs/lab-b/export/csv?full=true", headers=admin).status_code == 403
    assert "B private" not in client.get("/labs/lab-b/projects", headers=admin).text
    assert "B secret" not in client.get("/labs/lab-b/specimens", headers=admin).text


def test_a_member_of_the_second_laboratory_sees_everything_there(client, db, password_hash, labs):
    headers = member_of_second(db, password_hash, labs)
    titles = {p["title"] for p in client.get("/labs/lab-b/projects", headers=headers).json()}
    assert titles == {"B public", "B private"}
    assert "B secret" in client.get("/labs/lab-b/specimens", headers=headers).text


def test_that_member_is_a_visitor_in_the_first_laboratory(client, admin, db, password_hash, labs):
    headers = member_of_second(db, password_hash, labs)
    create_project(client, admin, title="Hidden", visibility="private")
    assert client.get("/labs/ufmg/projects", headers=headers).json() == []
    assert client.post("/labs/ufmg/projects", json=project_body(), headers=headers).status_code == 403


def test_a_user_of_two_laboratories_has_a_role_in_each(client, admin, db, password_hash, labs):
    user = db.query(models.User).filter_by(email="admin@lab.br").one()
    db.add(models.Membership(user_id=user.id, laboratory_id=labs["second"].id, role="researcher"))
    db.commit()
    project = client.post("/labs/lab-b/projects", json=project_body(title="Made in B"), headers=admin)
    assert project.status_code == 201
    assert client.delete(f"/labs/lab-b/projects/{project.json()['id']}", headers=admin).status_code == 403
    mine = client.post("/labs/ufmg/projects", json=project_body(title="Made in first"), headers=admin).json()
    assert client.delete(f"/labs/ufmg/projects/{mine['id']}", headers=admin).status_code == 204


def test_what_is_created_goes_to_the_laboratory_in_the_address(client, db, password_hash, labs):
    headers = member_of_second(db, password_hash, labs)
    project = client.post("/labs/lab-b/projects", json=project_body(), headers=headers).json()
    specimen = client.post("/labs/lab-b/specimens", json=specimen_body("NEW-1", project_id=project["id"]), headers=headers).json()
    assert db.get(models.Project, project["id"]).laboratory_id == labs["second"].id
    assert db.get(models.Specimen, specimen["id"]).laboratory_id == labs["second"].id


# ---------- a laboratory cannot reach another one's records by id ----------
def test_a_project_id_of_another_laboratory_is_a_404_in_this_address(client, admin, labs):
    other = labs["projects"]["public"]
    response = client.put(f"/labs/ufmg/projects/{other}", json={"title": "x"}, headers=admin)
    assert response.status_code == 404 and error_code(response) == "project_not_found"
    assert client.delete(f"/labs/ufmg/projects/{other}", headers=admin).status_code == 404


def test_a_specimen_cannot_be_put_in_a_project_of_another_laboratory_through_the_address(client, admin, labs):
    response = client.post("/labs/ufmg/specimens", json=specimen_body("X-1", project_id=labs["projects"]["public"]), headers=admin)
    assert response.status_code == 404 and error_code(response) == "project_not_found"


def test_the_same_catalog_number_works_in_two_laboratories_through_the_addresses(client, admin, db, password_hash, labs):
    headers = member_of_second(db, password_hash, labs)
    assert client.post("/labs/ufmg/specimens", json=specimen_body("SAME-1"), headers=admin).status_code == 201
    assert client.post("/labs/lab-b/specimens", json=specimen_body("SAME-1"), headers=headers).status_code == 201
    assert client.post("/labs/lab-b/specimens", json=specimen_body("SAME-1"), headers=headers).status_code == 400


# ---------- exports and the rest ----------
def test_the_csv_of_a_laboratory_has_only_its_public_data(client, labs):
    rows = list(csv.reader(io.StringIO(client.get("/labs/lab-b/export/csv").content.decode("utf-8-sig"))))
    assert {r[0] for r in rows[1:]} == {"B-public"}


def test_the_darwin_core_of_a_laboratory_uses_its_own_codes(client, labs):
    archive = zipfile.ZipFile(io.BytesIO(client.get("/labs/lab-b/export/dwc").content))
    row = next(csv.DictReader(io.StringIO(archive.read("occurrence.csv").decode("utf-8"))))
    assert (row["institutionCode"], row["collectionCode"], row["license"]) == ("BBB", "COL-B", "http://b.test")
    assert row["occurrenceID"] == "BBB:COL-B:B-public"


def test_the_demo_image_is_looked_up_inside_the_laboratory(client, db, labs):
    db.query(models.Specimen).filter_by(catalog_number="B-public").update({"image_file": "B-public.svg"})
    db.commit()
    assert client.get("/labs/lab-b/demo/image/B-public.svg").status_code == 200
    assert client.get("/labs/ufmg/demo/image/B-public.svg").status_code == 404


def test_login_and_share_links_do_not_belong_to_a_laboratory(client, user):
    assert client.post("/login", json={"email": user["email"], "password": user["password"]}).status_code == 200
    assert client.get("/labs/ufmg/shared/anything").status_code == 404 and client.get("/shared/anything").status_code == 404


def test_resolve_laboratory(db, labs):
    assert authorization.resolve_laboratory(db, None).id == labs["first"].id
    assert authorization.resolve_laboratory(db, "lab-b").id == labs["second"].id
