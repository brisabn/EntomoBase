import pytest

import authorization
import models
from conftest import EMAIL, make_token
from helpers import create_project, create_specimen, error_code, project_body, specimen_body
from laboratories import default_laboratory


# a second laboratory with a project and a specimen of its own, created directly in the database
@pytest.fixture
def other_lab(db):
    default_laboratory(db)
    lab = models.Laboratory(slug="other", name="Other lab", institution="OTH", collection_code="COL", license="http://license.test", listed=True)
    db.add(lab)
    db.flush()
    projects = {}
    for visibility in ("private", "unlisted", "public"):
        project = models.Project(
            laboratory_id=lab.id, title=f"Other {visibility}", year=2025, insect_group="Coleoptera", visibility=visibility,
            share_token="other-secret-link" if visibility == "unlisted" else None,
        )
        db.add(project)
        db.flush()
        specimen = models.Specimen(
            laboratory_id=lab.id, catalog_number=f"OTHER-{visibility}", insect_order="Coleoptera", species="Dynastes hercules",
            project_id=project.id, collector="Other secret collector",
        )
        db.add(specimen)
        projects[visibility] = (project, specimen)
    db.commit()
    return {"lab": lab, "projects": projects}


# ---------- who is allowed to write ----------
WRITES = [
    ("post", "/projects", lambda: project_body()),
    ("post", "/specimens", lambda: specimen_body("W-1")),
    ("post", "/specimens/import?validate_names=false", lambda: {"rows": []}),
    ("post", "/taxonomy/validate", lambda: {"names": ["Apis mellifera"]}),
]


@pytest.mark.parametrize("method,path,body", WRITES)
def test_a_visitor_cannot_write(client, method, path, body):
    response = getattr(client, method)(path, json=body())
    assert response.status_code == 401 and error_code(response) == "missing_token"


@pytest.mark.parametrize("method,path,body", WRITES)
def test_someone_who_is_not_a_member_cannot_write(client, outsider, method, path, body):
    response = getattr(client, method)(path, json=body(), headers=outsider)
    assert response.status_code == 403 and error_code(response) == "forbidden"


@pytest.mark.parametrize("method,path,body", WRITES)
def test_a_researcher_can_use_the_write_routes(client, researcher, method, path, body):
    response = getattr(client, method)(path, json=body(), headers=researcher)
    assert response.status_code in (200, 201), response.text


def test_a_researcher_creates_edits_and_deletes_specimens(client, researcher):
    specimen = create_specimen(client, researcher, "R-1")
    assert client.put(f"/specimens/{specimen['id']}", json={"habitat": "forest"}, headers=researcher).status_code == 200
    assert client.delete(f"/specimens/{specimen['id']}", headers=researcher).status_code == 204


def test_a_researcher_creates_and_edits_projects(client, researcher):
    project = create_project(client, researcher)
    response = client.put(f"/projects/{project['id']}", json={"title": "Edited"}, headers=researcher)
    assert response.status_code == 200 and response.json()["title"] == "Edited"


def test_only_an_admin_deletes_a_project(client, admin, researcher, outsider):
    project = create_project(client, admin)
    assert client.delete(f"/projects/{project['id']}", headers=researcher).status_code == 403
    assert client.delete(f"/projects/{project['id']}", headers=outsider).status_code == 403
    assert client.delete(f"/projects/{project['id']}").status_code == 401
    assert client.delete(f"/projects/{project['id']}", headers=admin).status_code == 204


def test_a_user_who_is_not_a_member_cannot_edit_or_delete_what_they_can_see(client, admin, outsider):
    project = create_project(client, admin, visibility="public")
    specimen = create_specimen(client, admin, "PUB-1", project_id=project["id"])
    assert client.put(f"/projects/{project['id']}", json={"title": "x"}, headers=outsider).status_code == 403
    assert client.put(f"/specimens/{specimen['id']}", json={"habitat": "x"}, headers=outsider).status_code == 403
    assert client.delete(f"/specimens/{specimen['id']}", headers=outsider).status_code == 403


def test_a_visitor_gets_401_on_update_and_delete(client, admin):
    project = create_project(client, admin)
    specimen = create_specimen(client, admin, "S-1", project_id=project["id"])
    assert client.put(f"/projects/{project['id']}", json={"title": "x"}).status_code == 401
    assert client.put(f"/specimens/{specimen['id']}", json={"habitat": "x"}).status_code == 401
    assert client.delete(f"/specimens/{specimen['id']}").status_code == 401


# ---------- the role comes from the database, not from the token ----------
def test_removing_a_member_takes_effect_on_the_next_request(client, researcher, db):
    assert client.post("/projects", json=project_body(), headers=researcher).status_code == 201
    db.query(models.Membership).filter(models.Membership.role == "researcher").delete()
    db.commit()
    response = client.post("/projects", json=project_body(), headers=researcher)
    assert response.status_code == 403


def test_changing_a_role_takes_effect_on_the_next_request(client, admin, db):
    project = create_project(client, admin)
    db.query(models.Membership).update({"role": "researcher"})
    db.commit()
    assert client.delete(f"/projects/{project['id']}", headers=admin).status_code == 403


def test_a_token_for_a_deleted_user_is_expired(client, admin, db):
    db.query(models.Membership).delete()
    db.query(models.User).delete()
    db.commit()
    response = client.post("/projects", json=project_body(), headers=admin)
    assert response.status_code == 401 and error_code(response) == "session_expired"


def test_a_token_without_a_subject_is_not_valid(client, user):
    import jwt
    import settings
    token = jwt.encode({"exp": 9999999999}, settings.SECRET_KEY, algorithm="HS256")
    response = client.post("/projects", json=project_body(), headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401 and error_code(response) == "session_expired"


def test_a_super_admin_has_no_access_to_the_data_of_a_laboratory_without_a_membership(client, password_hash, db):
    from conftest import add_user
    add_user("super@lab.br", password_hash)
    db.query(models.User).filter_by(email="super@lab.br").update({"is_superadmin": True})
    db.commit()
    headers = {"Authorization": f"Bearer {make_token(email='super@lab.br')}"}
    response = client.post("/projects", json=project_body(), headers=headers)
    assert response.status_code == 403


# ---------- helpers of the module ----------
def test_roles_are_a_closed_list():
    assert models.ROLES == ("admin", "researcher")
    assert models.VISIBILITIES == ("private", "unlisted", "public")


def test_context_properties(db):
    lab = default_laboratory(db)
    assert authorization.Context(lab).is_member is False
    assert authorization.Context(lab, role="researcher").is_member is True
    assert authorization.Context(lab, role="researcher").is_admin is False
    assert authorization.Context(lab, role="admin").is_admin is True


def test_the_role_of_someone_without_a_user_is_none(db):
    assert authorization.role_in(db, None, default_laboratory(db)) is None


def test_set_visibility_manages_the_share_token():
    project = models.Project()
    authorization.set_visibility(project, "unlisted")
    token = project.share_token
    assert token and project.visibility == "unlisted"
    authorization.set_visibility(project, "unlisted")
    assert project.share_token == token
    authorization.set_visibility(project, "public")
    assert project.share_token is None and project.visibility == "public"


def test_new_share_tokens_are_long_and_different():
    tokens = {authorization.new_share_token() for _ in range(50)}
    assert len(tokens) == 50 and all(len(t) >= 24 for t in tokens)


def test_the_superadmin_dependency(db, password_hash):
    from fastapi import HTTPException
    from conftest import add_user
    add_user("someone@lab.br", password_hash)
    user = db.query(models.User).filter_by(email="someone@lab.br").one()
    with pytest.raises(HTTPException) as refused:
        authorization.require_superadmin(user)
    assert refused.value.status_code == 403
    user.is_superadmin = True
    assert authorization.require_superadmin(user) is user


def test_the_admin_dependency(db):
    from fastapi import HTTPException
    lab = default_laboratory(db)
    with pytest.raises(HTTPException) as refused:
        authorization.require_admin(authorization.Context(lab, role="researcher"))
    assert refused.value.status_code == 403
    context = authorization.Context(lab, role="admin")
    assert authorization.require_admin(context) is context


# ---------- isolation: another laboratory is invisible ----------
def test_another_laboratorys_data_never_appears_in_lists(client, admin, other_lab):
    for headers in ({}, admin):
        assert "Other" not in client.get("/projects", headers=headers).text
        assert "OTHER-" not in client.get("/specimens", headers=headers).text
        assert "OTHER-" not in client.get("/export/csv", headers=headers).text
    assert "OTHER-" not in client.get("/export/csv?full=true", headers=admin).text


def test_another_laboratorys_data_is_not_in_the_darwin_core_export(client, other_lab):
    import io
    import zipfile
    archive = zipfile.ZipFile(io.BytesIO(client.get("/export/dwc").content))
    assert "OTHER" not in archive.read("occurrence.csv").decode("utf-8")


def test_another_laboratorys_projects_and_specimens_are_a_404_even_for_a_member(client, admin, other_lab):
    for visibility, (project, specimen) in other_lab["projects"].items():
        for response in (
            client.put(f"/projects/{project.id}", json={"title": "hacked"}, headers=admin),
            client.delete(f"/projects/{project.id}", headers=admin),
        ):
            assert response.status_code == 404 and error_code(response) == "project_not_found", visibility
        for response in (
            client.put(f"/specimens/{specimen.id}", json={"habitat": "hacked"}, headers=admin),
            client.delete(f"/specimens/{specimen.id}", headers=admin),
        ):
            assert response.status_code == 404 and error_code(response) == "specimen_not_found", visibility


def test_nothing_of_another_laboratory_was_changed(client, admin, other_lab, db):
    for project, specimen in other_lab["projects"].values():
        client.put(f"/projects/{project.id}", json={"title": "hacked"}, headers=admin)
        client.put(f"/specimens/{specimen.id}", json={"habitat": "hacked"}, headers=admin)
        client.delete(f"/specimens/{specimen.id}", headers=admin)
    db.expire_all()
    assert db.query(models.Project).filter(models.Project.title == "hacked").count() == 0
    assert db.query(models.Specimen).filter(models.Specimen.habitat == "hacked").count() == 0
    assert db.query(models.Specimen).filter(models.Specimen.laboratory_id == other_lab["lab"].id).count() == 3


def test_a_specimen_cannot_be_created_in_a_project_of_another_laboratory(client, admin, other_lab):
    project, _ = other_lab["projects"]["public"]
    response = client.post("/specimens", json=specimen_body("X-1", project_id=project.id), headers=admin)
    assert response.status_code == 404 and error_code(response) == "project_not_found"


def test_a_specimen_cannot_be_moved_to_a_project_of_another_laboratory(client, admin, other_lab):
    project, _ = other_lab["projects"]["public"]
    mine = create_specimen(client, admin, "MINE-1")
    response = client.put(f"/specimens/{mine['id']}", json={"project_id": project.id}, headers=admin)
    assert response.status_code == 404 and error_code(response) == "project_not_found"


def test_importing_into_a_project_of_another_laboratory_is_refused(client, admin, other_lab):
    project, _ = other_lab["projects"]["public"]
    row = {"catalog_number": "IMP-1", "insect_order": "Coleoptera", "species": "Dynastes hercules"}
    response = client.post("/specimens/import?validate_names=false", json={"rows": [row], "project_id": project.id}, headers=admin)
    assert response.status_code == 404 and error_code(response) == "project_not_found"


def test_a_row_that_names_a_project_of_another_laboratory_is_an_error(client, admin, other_lab):
    project, _ = other_lab["projects"]["public"]
    row = {"catalog_number": "IMP-1", "insect_order": "Coleoptera", "species": "Dynastes hercules", "project_id": project.id}
    report = client.post("/specimens/import?dry_run=true&validate_names=false", json={"rows": [row]}, headers=admin).json()
    assert report["errors"][0]["problems"][0]["code"] == "unknown_project"


def test_importing_never_touches_the_specimens_of_another_laboratory(client, admin, other_lab, db):
    row = {"catalog_number": "OTHER-public", "insect_order": "Coleoptera", "species": "Apis mellifera", "habitat": "overwritten"}
    report = client.post("/specimens/import?validate_names=false", json={"rows": [row], "duplicates": "update"}, headers=admin).json()
    assert (report["created"], report["updated"]) == (1, 0)
    other = db.query(models.Specimen).filter_by(laboratory_id=other_lab["lab"].id, catalog_number="OTHER-public").one()
    assert other.habitat is None and other.species == "Dynastes hercules"


def test_the_share_link_of_another_laboratory_still_works_by_its_token(client, other_lab):
    response = client.get("/shared/other-secret-link")
    assert response.status_code == 200 and response.json()["title"] == "Other unlisted"
    assert "Other secret collector" not in client.get("/shared/other-secret-link/specimens").text


def test_the_darwin_core_uses_the_data_of_the_laboratory(client, admin, db):
    import csv
    import io
    import zipfile
    lab = default_laboratory(db)
    lab.institution, lab.collection_code, lab.license = "INST", "COLL", "http://my-license.test"
    db.commit()
    project = create_project(client, admin, visibility="public")
    create_specimen(client, admin, "DW-1", project_id=project["id"])
    archive = zipfile.ZipFile(io.BytesIO(client.get("/export/dwc").content))
    row = next(csv.DictReader(io.StringIO(archive.read("occurrence.csv").decode("utf-8"))))
    assert (row["institutionCode"], row["collectionCode"], row["license"]) == ("INST", "COLL", "http://my-license.test")
    assert row["occurrenceID"] == "INST:COLL:DW-1"


def test_the_admin_email_in_the_fixture_is_the_one_with_the_membership(db, user):
    membership = db.query(models.Membership).one()
    assert db.get(models.User, membership.user_id).email == EMAIL and membership.role == "admin"


def test_the_required_user_dependency(db, user):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as missing:
        authorization.required_user(None, db)
    assert (missing.value.status_code, missing.value.detail["code"]) == (401, "missing_token")
    with pytest.raises(HTTPException) as expired:
        authorization.required_user("Bearer garbage", db)
    assert (expired.value.status_code, expired.value.detail["code"]) == (401, "session_expired")
    assert authorization.required_user(f"Bearer {make_token()}", db).email == EMAIL


# ---------- gaps found by mutation testing ----------
def test_a_member_of_another_laboratory_is_not_a_member_here(client, password_hash, db, other_lab):
    from conftest import add_user
    add_user("elsewhere@lab.br", password_hash)
    user = db.query(models.User).filter_by(email="elsewhere@lab.br").one()
    db.add(models.Membership(user_id=user.id, laboratory_id=other_lab["lab"].id, role="admin"))
    db.commit()
    headers = {"Authorization": f"Bearer {make_token(email='elsewhere@lab.br')}"}
    assert client.post("/projects", json=project_body(), headers=headers).status_code == 403
    assert client.get("/export/csv?full=true", headers=headers).status_code == 403


def test_a_project_goes_to_the_laboratory_of_the_request_whatever_its_id(client, password_hash, db):
    from conftest import add_user
    lab = models.Laboratory(id=7, slug="seven", name="Seven", institution="S", collection_code="S", license="x", listed=True)
    db.add(lab)
    db.commit()
    add_user("seven@lab.br", password_hash)
    user = db.query(models.User).filter_by(email="seven@lab.br").one()
    db.add(models.Membership(user_id=user.id, laboratory_id=7, role="admin"))
    db.commit()
    headers = {"Authorization": f"Bearer {make_token(email='seven@lab.br')}"}
    project = client.post("/projects", json=project_body(), headers=headers).json()
    specimen = client.post("/specimens", json=specimen_body("S-1", project_id=project["id"]), headers=headers).json()
    assert db.get(models.Project, project["id"]).laboratory_id == 7
    assert db.get(models.Specimen, specimen["id"]).laboratory_id == 7


# a public project should never have a share token, but if the data ever says otherwise it must not leak or open
def test_a_stray_share_token_on_a_public_project_is_not_sent_to_visitors(client, admin, db):
    project = create_project(client, admin, visibility="public")
    db.query(models.Project).filter_by(id=project["id"]).update({"share_token": "stray-token"})
    db.commit()
    assert "stray-token" not in client.get("/projects").text
    assert "stray-token" in client.get("/projects", headers=admin).text


def test_a_stray_share_token_does_not_open_a_public_project(client, admin, db):
    project = create_project(client, admin, visibility="public")
    db.query(models.Project).filter_by(id=project["id"]).update({"share_token": "stray-token"})
    db.commit()
    assert client.get("/shared/stray-token").status_code == 404


def test_the_demo_image_of_a_private_specimen_is_not_served_even_to_a_member(client, admin):
    project = create_project(client, admin, visibility="private")
    create_specimen(client, admin, "PRIV-IMG", project_id=project["id"], image_file="PRIV-IMG.svg")
    assert client.get("/demo/image/PRIV-IMG.svg", headers=admin).status_code == 404
