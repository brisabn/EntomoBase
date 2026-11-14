from datetime import datetime, timedelta

import pytest

import models
from conftest import EMAIL, RESEARCHER_EMAIL, add_user, make_token
from email_confirmation import utc_now
from helpers import project_body


def create(client, headers, slug="ufmg", **overrides):
    response = client.post(f"/labs/{slug}/projects", json=project_body(**overrides), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def publish(client, headers, project_id, visibility, slug="ufmg"):
    return client.put(f"/labs/{slug}/projects/{project_id}", json={"visibility": visibility}, headers=headers)


def history(client, headers, slug="ufmg", **params):
    return client.get(f"/labs/{slug}/visibility-history", params=params, headers=headers)


def second_lab(db, admin_email):
    lab = models.Laboratory(slug="lab-b", name="Lab B", institution="B", collection_code="B", license="x", listed=True)
    db.add(lab)
    db.flush()
    db.add(models.Membership(user_id=db.query(models.User).filter_by(email=admin_email).one().id, laboratory_id=lab.id, role="admin"))
    db.commit()


# ---------- what is kept ----------
def test_creating_a_project_records_who_created_it_and_how_visible(client, admin):
    project = create(client, admin, title="New beetles", visibility="private")
    [entry] = history(client, admin).json()
    assert (entry["project_id"], entry["project_title"], entry["user_email"]) == (project["id"], "New beetles", EMAIL)
    assert (entry["from_visibility"], entry["to_visibility"]) == (None, "private")
    assert set(entry) == {"id", "project_id", "project_title", "user_email", "from_visibility", "to_visibility", "changed_at"}


def test_a_project_created_public_says_so(client, admin):
    create(client, admin, visibility="public")
    assert history(client, admin).json()[0]["to_visibility"] == "public"


def test_each_change_is_kept_newest_first(client, admin):
    project = create(client, admin, visibility="private")
    for visibility in ("unlisted", "public", "private"):
        publish(client, admin, project["id"], visibility)
    steps = [(e["from_visibility"], e["to_visibility"]) for e in history(client, admin).json()]
    assert steps == [("public", "private"), ("unlisted", "public"), ("private", "unlisted"), (None, "private")]


def test_the_time_of_each_change_is_kept(client, admin):
    create(client, admin)
    changed = history(client, admin).json()[0]["changed_at"]
    assert abs((datetime.fromisoformat(changed) - utc_now()).total_seconds()) < 60


def test_a_researcher_who_publishes_is_named(client, admin, researcher):
    project = create(client, admin, visibility="private")
    publish(client, researcher, project["id"], "public")
    latest = history(client, admin).json()[0]
    assert (latest["user_email"], latest["to_visibility"]) == (RESEARCHER_EMAIL, "public")


def test_nothing_is_kept_when_the_visibility_does_not_change(client, admin):
    project = create(client, admin, visibility="public")
    publish(client, admin, project["id"], "public")
    client.put(f"/labs/ufmg/projects/{project['id']}", json={"title": "Renamed"}, headers=admin)
    client.put(f"/labs/ufmg/projects/{project['id']}", json={"visibility": None}, headers=admin)
    assert len(history(client, admin).json()) == 1


def test_a_refused_change_is_not_kept(client, admin, outsider):
    project = create(client, admin, visibility="private")
    assert publish(client, outsider, project["id"], "public").status_code == 403
    assert publish(client, admin, project["id"], "everyone").status_code == 422
    assert len(history(client, admin).json()) == 1


def test_each_entry_keeps_the_title_the_project_had_then(client, admin):
    project = create(client, admin, title="Old title", visibility="private")
    client.put(f"/labs/ufmg/projects/{project['id']}", json={"title": "New title", "visibility": "public"}, headers=admin)
    titles = [e["project_title"] for e in history(client, admin).json()]
    assert titles == ["New title", "Old title"]


def test_the_history_of_a_deleted_project_stays_without_the_link(client, admin):
    project = create(client, admin, title="Gone soon", visibility="public")
    assert client.delete(f"/labs/ufmg/projects/{project['id']}", headers=admin).status_code == 204
    [entry] = history(client, admin).json()
    assert (entry["project_id"], entry["project_title"]) == (None, "Gone soon")


def test_one_project_can_be_asked_for(client, admin):
    first = create(client, admin, title="First")
    create(client, admin, title="Second")
    entries = history(client, admin, project_id=first["id"]).json()
    assert [e["project_title"] for e in entries] == ["First"]
    assert history(client, admin, project_id=99999).json() == []


def test_the_list_stops_at_its_limit(client, admin, db, monkeypatch):
    import main
    monkeypatch.setattr(main, "VISIBILITY_HISTORY_LIMIT", 3)
    for n in range(5):
        create(client, admin, title=f"P{n}")
    assert [e["project_title"] for e in history(client, admin).json()] == ["P4", "P3", "P2"]


def test_the_newest_comes_first_even_with_the_same_time(client, admin, db):
    create(client, admin, title="A")
    create(client, admin, title="B")
    db.query(models.VisibilityChange).update({"changed_at": utc_now() - timedelta(days=1)})
    db.commit()
    assert [e["project_title"] for e in history(client, admin).json()] == ["B", "A"]


# ---------- who sees it ----------
def test_only_the_admins_of_the_laboratory_see_it(client, admin, researcher, outsider, superadmin):
    create(client, admin)
    for headers, status in ((researcher, 403), (outsider, 403), (superadmin, 403), ({}, 401)):
        assert history(client, headers).status_code == status


def test_there_is_no_address_without_the_laboratory(client, admin):
    assert client.get("/visibility-history", headers=admin).status_code == 404


def test_each_laboratory_sees_only_its_own(client, admin, password_hash, db):
    add_user("boss@lab.br", password_hash)
    second_lab(db, "boss@lab.br")
    boss = {"Authorization": f"Bearer {make_token(email='boss@lab.br')}"}
    create(client, admin, title="In the first")
    other = create(client, boss, slug="lab-b", title="In the second")
    assert [e["project_title"] for e in history(client, admin).json()] == ["In the first"]
    assert [e["project_title"] for e in history(client, boss, slug="lab-b").json()] == ["In the second"]
    # a project of the other laboratory is simply not in this list
    assert history(client, admin, project_id=other["id"]).json() == []


@pytest.mark.parametrize("bad", ["abc", "1.5"])
def test_a_bad_project_id_is_a_422(client, admin, bad):
    assert history(client, admin, project_id=bad).status_code == 422
