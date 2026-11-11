import csv
import io
import zipfile

import pytest

import schemas
from helpers import create_project, create_specimen, error_code

INTERNAL = {
    "collector": "Secret Collector", "field_number": "C123", "storage_location": "Cabinet 9",
    "loan_status": "emprestado", "loaned_to": "Secret Museum", "loan_date": "2025-01-02", "internal_notes": "Secret note",
}


# one project of each visibility, each with a specimen, plus a specimen with no project
@pytest.fixture
def world(client, admin):
    public = create_project(client, admin, title="Public project", visibility="public")
    private = create_project(client, admin, title="Private project", visibility="private")
    unlisted = create_project(client, admin, title="Unlisted project", visibility="unlisted")
    create_specimen(client, admin, "PUB-1", project_id=public["id"], latitude=-19.5, longitude=-43.5, **INTERNAL)
    create_specimen(client, admin, "PRIV-1", project_id=private["id"], **INTERNAL)
    create_specimen(client, admin, "LINK-1", project_id=unlisted["id"], **INTERNAL)
    create_specimen(client, admin, "FREE-1", **INTERNAL)
    return {"public": public, "private": private, "unlisted": unlisted}


# ---------- projects ----------
def test_visitor_only_sees_public_projects(client, world):
    assert [p["title"] for p in client.get("/projects").json()] == ["Public project"]


def test_a_member_sees_every_project_of_the_laboratory(client, admin, world):
    titles = {p["title"] for p in client.get("/projects", headers=admin).json()}
    assert titles == {"Public project", "Private project", "Unlisted project"}


def test_a_researcher_sees_every_project_of_the_laboratory(client, researcher, world):
    assert len(client.get("/projects", headers=researcher).json()) == 3


def test_a_logged_in_user_who_is_not_a_member_sees_only_what_is_public(client, outsider, world):
    assert [p["title"] for p in client.get("/projects", headers=outsider).json()] == ["Public project"]


def test_a_garbage_token_is_treated_as_a_visitor(client, world):
    response = client.get("/projects", headers={"Authorization": "Bearer garbage"})
    assert [p["title"] for p in response.json()] == ["Public project"]


def test_a_visitor_cannot_ask_for_hidden_projects_by_filter(client, world):
    assert client.get("/projects?visibility=private").json() == []
    assert client.get("/projects?visibility=unlisted").json() == []


def test_a_member_can_filter_by_visibility(client, admin, world):
    assert [p["title"] for p in client.get("/projects?visibility=private", headers=admin).json()] == ["Private project"]


def test_the_status_filter_works_for_anyone_because_it_is_not_secret(client, admin, world):
    client.put(f"/projects/{world['public']['id']}", json={"finished": True}, headers=admin)
    assert [p["title"] for p in client.get("/projects?finished=true").json()] == ["Public project"]
    assert client.get("/projects?finished=false").json() == []


def test_the_share_token_is_only_sent_to_members(client, admin, outsider, world):
    members = {p["title"]: p for p in client.get("/projects", headers=admin).json()}
    assert members["Unlisted project"]["share_token"]
    assert members["Public project"]["share_token"] is None
    assert all(p["share_token"] is None for p in client.get("/projects").json())
    assert all(p["share_token"] is None for p in client.get("/projects", headers=outsider).json())


# ---------- specimens ----------
def test_visitor_only_sees_specimens_of_public_projects(client, world):
    assert {s["catalog_number"] for s in client.get("/specimens").json()} == {"PUB-1"}


def test_a_specimen_without_a_project_is_private(client, world, outsider):
    assert "FREE-1" not in client.get("/specimens").text
    assert "FREE-1" not in client.get("/specimens", headers=outsider).text


def test_a_visitor_cannot_list_a_hidden_project_by_id(client, world):
    for key in ("private", "unlisted"):
        assert client.get(f"/specimens?project_id={world[key]['id']}").json() == []


def test_a_member_sees_every_specimen(client, admin, world):
    codes = {s["catalog_number"] for s in client.get("/specimens", headers=admin).json()}
    assert codes == {"PUB-1", "PRIV-1", "LINK-1", "FREE-1"}


def test_a_visitor_never_receives_internal_fields(client, world):
    for specimen in client.get("/specimens").json():
        assert not (set(specimen) & schemas.INTERNAL_FIELDS), set(specimen) & schemas.INTERNAL_FIELDS
    assert "Secret" not in client.get("/specimens").text


def test_a_logged_in_user_who_is_not_a_member_never_receives_internal_fields(client, outsider, world):
    assert "Secret" not in client.get("/specimens", headers=outsider).text


def test_a_member_receives_internal_fields(client, admin, world):
    specimen = next(s for s in client.get("/specimens", headers=admin).json() if s["catalog_number"] == "PUB-1")
    assert specimen["collector"] == "Secret Collector"
    assert specimen["internal_notes"] == "Secret note"


def test_every_internal_field_is_covered_by_these_tests():
    assert set(INTERNAL) == schemas.INTERNAL_FIELDS


# ---------- unlisted: only with the link ----------
def share_token(client, admin, project):
    return next(p for p in client.get("/projects", headers=admin).json() if p["id"] == project["id"])["share_token"]


def test_an_unlisted_project_opens_with_its_share_token(client, admin, world):
    token = share_token(client, admin, world["unlisted"])
    response = client.get(f"/shared/{token}")
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Unlisted project" and body["visibility"] == "unlisted"
    assert body["share_token"] is None


def test_the_shared_specimens_have_no_internal_fields(client, admin, world):
    token = share_token(client, admin, world["unlisted"])
    response = client.get(f"/shared/{token}/specimens")
    assert [s["catalog_number"] for s in response.json()] == ["LINK-1"]
    assert "Secret" not in response.text


def test_the_share_token_is_not_the_numeric_id(client, admin, world):
    token = share_token(client, admin, world["unlisted"])
    assert token != str(world["unlisted"]["id"]) and len(token) >= 24
    assert client.get(f"/shared/{world['unlisted']['id']}").status_code == 404


def test_a_wrong_token_is_a_404(client, world):
    response = client.get("/shared/not-a-real-token")
    assert response.status_code == 404 and error_code(response) == "project_not_found"
    assert client.get("/shared/not-a-real-token/specimens").status_code == 404


def test_public_and_private_projects_have_no_share_link(client, admin, world, db):
    import models
    assert db.get(models.Project, world["public"]["id"]).share_token is None
    assert db.get(models.Project, world["private"]["id"]).share_token is None


def test_the_unlisted_project_is_in_no_visitor_listing_or_export(client, world):
    assert "LINK-1" not in client.get("/specimens").text
    assert "Unlisted" not in client.get("/projects").text
    assert "LINK-1" not in client.get("/export/csv").text
    archive = zipfile.ZipFile(io.BytesIO(client.get("/export/dwc").content))
    assert "LINK-1" not in archive.read("occurrence.csv").decode("utf-8")


# ---------- changing visibility ----------
def get_project(client, admin, project):
    return next(p for p in client.get("/projects", headers=admin).json() if p["id"] == project["id"])


def test_publishing_makes_a_project_visible_to_visitors(client, admin, world):
    client.put(f"/projects/{world['private']['id']}", json={"visibility": "public"}, headers=admin)
    assert {p["title"] for p in client.get("/projects").json()} == {"Public project", "Private project"}
    assert "PRIV-1" in client.get("/specimens").text


def test_unpublishing_hides_a_project_again(client, admin, world):
    client.put(f"/projects/{world['public']['id']}", json={"visibility": "private"}, headers=admin)
    assert client.get("/projects").json() == []
    assert client.get("/specimens").json() == []


def test_a_researcher_can_publish(client, researcher, world):
    response = client.put(f"/projects/{world['private']['id']}", json={"visibility": "public"}, headers=researcher)
    assert response.status_code == 200 and response.json()["visibility"] == "public"


def test_becoming_unlisted_creates_a_share_token_and_leaving_it_removes_the_token(client, admin, world):
    token = share_token(client, admin, world["unlisted"])
    client.put(f"/projects/{world['unlisted']['id']}", json={"visibility": "public"}, headers=admin)
    assert get_project(client, admin, world["unlisted"])["share_token"] is None
    assert client.get(f"/shared/{token}").status_code == 404


def test_becoming_unlisted_again_creates_a_different_link(client, admin, world):
    old = share_token(client, admin, world["unlisted"])
    client.put(f"/projects/{world['unlisted']['id']}", json={"visibility": "private"}, headers=admin)
    client.put(f"/projects/{world['unlisted']['id']}", json={"visibility": "unlisted"}, headers=admin)
    new = share_token(client, admin, world["unlisted"])
    assert new and new != old
    assert client.get(f"/shared/{old}").status_code == 404 and client.get(f"/shared/{new}").status_code == 200


def test_saving_an_unlisted_project_again_keeps_its_link(client, admin, world):
    token = share_token(client, admin, world["unlisted"])
    client.put(f"/projects/{world['unlisted']['id']}", json={"visibility": "unlisted", "title": "Renamed"}, headers=admin)
    assert share_token(client, admin, world["unlisted"]) == token


def test_editing_without_visibility_leaves_it_alone(client, admin, world):
    client.put(f"/projects/{world['private']['id']}", json={"title": "Renamed"}, headers=admin)
    assert get_project(client, admin, world["private"])["visibility"] == "private"


def test_an_explicit_null_visibility_changes_nothing(client, admin, world):
    response = client.put(f"/projects/{world['public']['id']}", json={"visibility": None}, headers=admin)
    assert response.status_code == 200 and response.json()["visibility"] == "public"


def test_an_unknown_visibility_is_refused(client, admin, world):
    response = client.put(f"/projects/{world['public']['id']}", json={"visibility": "secret"}, headers=admin)
    assert response.status_code == 422
    assert client.post("/projects", json={"title": "T", "year": 2025, "insect_group": "G", "visibility": "secret"}, headers=admin).status_code == 422


# ---------- exports ----------
def read_csv(response):
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))


def test_public_csv_has_only_public_projects_and_no_internal_columns(client, world):
    rows = read_csv(client.get("/export/csv"))
    assert {r[0] for r in rows[1:]} == {"PUB-1"}
    assert "Coletor" not in rows[0]
    assert "Secret" not in client.get("/export/csv").text


def test_the_normal_csv_stays_public_even_for_a_member(client, admin, world):
    rows = read_csv(client.get("/export/csv", headers=admin))
    assert {r[0] for r in rows[1:]} == {"PUB-1"}
    assert "Secret" not in client.get("/export/csv", headers=admin).text


def test_full_csv_requires_login(client, world):
    response = client.get("/export/csv?full=true")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "full_csv_requires_login"


def test_full_csv_for_a_garbage_token_is_refused(client, world):
    response = client.get("/export/csv?full=true", headers={"Authorization": "Bearer garbage"})
    assert response.status_code == 401


def test_full_csv_is_refused_to_someone_who_is_not_a_member(client, outsider, world):
    response = client.get("/export/csv?full=true", headers=outsider)
    assert response.status_code == 403 and error_code(response) == "forbidden"
    assert "Secret" not in response.text


def test_full_csv_has_every_specimen_and_internal_columns(client, admin, world):
    rows = read_csv(client.get("/export/csv?full=true", headers=admin))
    assert {r[0] for r in rows[1:]} == {"PUB-1", "PRIV-1", "LINK-1", "FREE-1"}
    assert "Coletor" in rows[0] and "Notas Internas" in rows[0]
    assert "Secret Collector" in {cell for row in rows for cell in row}


def test_darwin_core_is_always_public(client, admin, world):
    for headers in ({}, admin):
        archive = zipfile.ZipFile(io.BytesIO(client.get("/export/dwc", headers=headers).content))
        content = archive.read("occurrence.csv").decode("utf-8")
        assert "PUB-1" in content
        for hidden in ("PRIV-1", "LINK-1", "FREE-1"):
            assert hidden not in content
        for secret in ("Secret", "C123", "Cabinet 9"):
            assert secret not in content


def test_the_demo_image_of_a_hidden_specimen_is_not_served(client, admin, world):
    project = create_project(client, admin, title="Hidden", visibility="private")
    create_specimen(client, admin, "IMG-HIDDEN", project_id=project["id"], image_file="IMG-HIDDEN.svg")
    assert client.get("/demo/image/IMG-HIDDEN.svg").status_code == 404
