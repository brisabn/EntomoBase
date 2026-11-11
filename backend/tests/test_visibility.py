import csv
import io
import zipfile

import pytest

import schemas
from helpers import create_project, create_specimen

INTERNAL = {
    "collector": "Secret Collector", "field_number": "C123", "storage_location": "Cabinet 9",
    "loan_status": "emprestado", "loaned_to": "Secret Museum", "loan_date": "2025-01-02", "internal_notes": "Secret note",
}


@pytest.fixture
def world(client, admin):
    finished = create_project(client, admin, title="Finished project", finished=True)
    running = create_project(client, admin, title="Running project", finished=False)
    create_specimen(client, admin, "PUB-1", project_id=finished["id"], latitude=-19.5, longitude=-43.5, **INTERNAL)
    create_specimen(client, admin, "RUN-1", project_id=running["id"], **INTERNAL)
    create_specimen(client, admin, "FREE-1", **INTERNAL)
    return {"finished": finished, "running": running}


# ---------- projects ----------
def test_visitor_only_sees_finished_projects(client, world):
    titles = [p["title"] for p in client.get("/projects").json()]
    assert titles == ["Finished project"]


def test_logged_in_user_sees_every_project(client, admin, world):
    titles = {p["title"] for p in client.get("/projects", headers=admin).json()}
    assert titles == {"Finished project", "Running project"}


def test_visitor_cannot_ask_for_unfinished_projects(client, world):
    assert [p["title"] for p in client.get("/projects?finished=false").json()] == ["Finished project"]


def test_logged_in_user_can_filter_by_status(client, admin, world):
    running = client.get("/projects?finished=false", headers=admin).json()
    assert [p["title"] for p in running] == ["Running project"]


def test_a_garbage_token_is_treated_as_a_visitor(client, world):
    response = client.get("/projects", headers={"Authorization": "Bearer garbage"})
    assert [p["title"] for p in response.json()] == ["Finished project"]


# ---------- specimens ----------
def test_visitor_does_not_see_specimens_of_unfinished_projects(client, world):
    codes = {s["catalog_number"] for s in client.get("/specimens").json()}
    assert codes == {"PUB-1", "FREE-1"}


def test_visitor_cannot_list_an_unfinished_project_by_id(client, world):
    assert client.get(f"/specimens?project_id={world['running']['id']}").json() == []


def test_logged_in_user_sees_every_specimen(client, admin, world):
    codes = {s["catalog_number"] for s in client.get("/specimens", headers=admin).json()}
    assert codes == {"PUB-1", "RUN-1", "FREE-1"}


def test_visitor_never_receives_internal_fields(client, world):
    for specimen in client.get("/specimens").json():
        assert not (set(specimen) & schemas.INTERNAL_FIELDS), set(specimen) & schemas.INTERNAL_FIELDS
    assert "Secret" not in client.get("/specimens").text


def test_logged_in_user_receives_internal_fields(client, admin, world):
    specimen = next(s for s in client.get("/specimens", headers=admin).json() if s["catalog_number"] == "PUB-1")
    assert specimen["collector"] == "Secret Collector"
    assert specimen["internal_notes"] == "Secret note"


def test_every_internal_field_is_covered_by_these_tests():
    assert set(INTERNAL) == schemas.INTERNAL_FIELDS


# ---------- exports ----------
def read_csv(response):
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))


def test_public_csv_hides_unfinished_projects_and_internal_columns(client, world):
    rows = read_csv(client.get("/export/csv"))
    assert {r[0] for r in rows[1:]} == {"PUB-1", "FREE-1"}
    assert "Coletor" not in rows[0]
    assert "Secret" not in client.get("/export/csv").text


def test_full_csv_requires_login(client, world):
    response = client.get("/export/csv?full=true")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "full_csv_requires_login"


def test_full_csv_for_a_garbage_token_is_refused(client, world):
    response = client.get("/export/csv?full=true", headers={"Authorization": "Bearer garbage"})
    assert response.status_code == 401


def test_full_csv_has_every_specimen_and_internal_columns(client, admin, world):
    rows = read_csv(client.get("/export/csv?full=true", headers=admin))
    assert {r[0] for r in rows[1:]} == {"PUB-1", "RUN-1", "FREE-1"}
    assert "Coletor" in rows[0] and "Notas Internas" in rows[0]
    assert "Secret Collector" in {cell for row in rows for cell in row}


def test_darwin_core_is_always_public(client, admin, world):
    for headers in ({}, admin):
        archive = zipfile.ZipFile(io.BytesIO(client.get("/export/dwc", headers=headers).content))
        content = archive.read("occurrence.csv").decode("utf-8")
        assert "PUB-1" in content and "FREE-1" in content
        assert "RUN-1" not in content
        for secret in ("Secret", "C123", "Cabinet 9"):
            assert secret not in content
