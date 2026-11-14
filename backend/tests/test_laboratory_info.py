import pytest

import models


def add_lab(db, slug, name, listed):
    db.add(models.Laboratory(slug=slug, name=name, institution="INST", collection_code="CODE", license="x", listed=listed))
    db.commit()


def test_a_laboratory_tells_its_public_data(client, user, db):
    add_lab(db, "lab-b", "Lab B", True)
    response = client.get("/labs/lab-b/laboratory")
    assert response.status_code == 200
    assert response.json() == {"slug": "lab-b", "name": "Lab B", "institution": "INST", "collection_code": "CODE",
                               "about": None, "contact_email": None, "team": []}


def test_an_unlisted_laboratory_answers_too(client, user, db):
    add_lab(db, "hidden", "Hidden lab", False)
    assert client.get("/labs/hidden/laboratory").json()["name"] == "Hidden lab"


def test_the_old_address_is_the_first_laboratory(client, user, db):
    add_lab(db, "aaa", "A first by name", True)
    assert client.get("/laboratory").json()["slug"] == "ufmg"


def test_an_unknown_laboratory_is_a_404(client, user):
    response = client.get("/labs/nowhere/laboratory")
    assert response.status_code == 404 and response.json()["detail"]["code"] == "lab_not_found"


def test_nothing_internal_is_sent(client, user, db):
    add_lab(db, "lab-b", "Lab B", False)
    body = client.get("/labs/lab-b/laboratory").json()
    assert set(body) == {"slug", "name", "institution", "collection_code", "about", "contact_email", "team"}
    assert "license" not in body and "listed" not in body


def test_members_and_strangers_get_the_same_answer(client, admin, outsider):
    assert client.get("/laboratory", headers=admin).json() == client.get("/laboratory", headers=outsider).json() == client.get("/laboratory").json()


# ---------- the About page, written by the admins ----------
ABOUT = {
    "about": "We study ants of the Cerrado.\n\nOur collection has 3,000 specimens.",
    "contact_email": "lab@ufmg.br",
    "team": [{"name": "Ana Lima", "role": "Coordinator"}, {"name": "Bruno Reis", "role": None}],
}


def update(client, headers, body, slug=None):
    return client.put(f"/labs/{slug}/laboratory" if slug else "/laboratory", json=body, headers=headers)


def test_an_admin_writes_the_about_page_and_everyone_sees_it(client, admin, db):
    response = update(client, admin, ABOUT)
    assert response.status_code == 200
    body = client.get("/laboratory").json()
    assert body["about"] == ABOUT["about"] and body["contact_email"] == "lab@ufmg.br"
    assert body["team"] == ABOUT["team"]
    assert response.json() == body


def test_the_team_keeps_its_order_and_trims_its_texts(client, admin):
    team = [{"name": "  Zé  ", "role": "  Student "}, {"name": "Amy", "role": ""}]
    assert update(client, admin, {"team": team}).json()["team"] == [{"name": "Zé", "role": "Student"}, {"name": "Amy", "role": None}]


def test_a_field_left_out_stays_as_it_was(client, admin):
    update(client, admin, ABOUT)
    body = update(client, admin, {"contact_email": "other@ufmg.br"}).json()
    assert body["about"] == ABOUT["about"] and body["team"] == ABOUT["team"] and body["contact_email"] == "other@ufmg.br"


def test_empty_presentation_and_contact_mean_none_and_an_empty_team_clears_it(client, admin):
    update(client, admin, ABOUT)
    body = update(client, admin, {"about": "   ", "contact_email": "", "team": []}).json()
    assert (body["about"], body["contact_email"], body["team"]) == (None, None, [])
    body = update(client, admin, {"about": None, "contact_email": None, "team": None}).json()
    assert (body["about"], body["contact_email"], body["team"]) == (None, None, [])


def test_the_name_and_institution_change_but_never_to_nothing(client, admin):
    body = update(client, admin, {"name": "  Ant Lab  ", "institution": "UFMG - ICB"}).json()
    assert (body["name"], body["institution"]) == ("Ant Lab", "UFMG - ICB")
    assert update(client, admin, {"name": None}).json()["name"] == "Ant Lab"
    assert update(client, admin, {"name": ""}).status_code == 422


def test_the_address_collection_code_license_and_list_stay(client, admin, db):
    update(client, admin, {"slug": "taken", "collection_code": "X", "license": "y", "listed": False})
    db.expire_all()
    lab = db.query(models.Laboratory).one()
    assert (lab.slug, lab.collection_code, lab.listed) == ("ufmg", "EntomoBase", True)
    assert lab.license.startswith("http://creativecommons.org")


def test_an_invalid_contact_is_refused_and_nothing_changes(client, admin):
    update(client, admin, ABOUT)
    response = update(client, admin, {"contact_email": "not an address", "about": "Changed"})
    assert response.status_code == 400 and response.json()["detail"]["code"] == "invalid_email"
    assert client.get("/laboratory").json()["about"] == ABOUT["about"]


@pytest.mark.parametrize("body", [
    {"about": "x" * 5001}, {"contact_email": "a" * 255}, {"team": [{"name": ""}]}, {"team": [{"role": "no name"}]},
    {"team": [{"name": "a" * 121}]}, {"team": [{"name": "A", "role": "r" * 121}]}, {"team": [{"name": f"P{n}"} for n in range(31)]},
    {"name": "n" * 201},
])
def test_limits_are_checked(client, admin, body):
    assert update(client, admin, body).status_code == 422


def test_thirty_people_fit(client, admin):
    assert len(update(client, admin, {"team": [{"name": f"P{n}"} for n in range(30)]}).json()["team"]) == 30


def test_only_admins_of_the_laboratory_write_it(client, admin, researcher, outsider, superadmin, db):
    for headers, status in ((researcher, 403), (outsider, 403), (superadmin, 403), ({}, 401)):
        assert update(client, headers, ABOUT).status_code == status
    assert client.get("/laboratory").json()["about"] is None


def test_an_admin_of_one_laboratory_does_not_write_another(client, admin, db):
    add_lab(db, "lab-b", "Lab B", True)
    assert update(client, admin, ABOUT, slug="lab-b").status_code == 403
    assert client.get("/labs/lab-b/laboratory").json()["about"] is None


def test_each_laboratory_has_its_own_page(client, admin, db):
    add_lab(db, "lab-b", "Lab B", True)
    update(client, admin, ABOUT, slug="ufmg")
    assert client.get("/labs/lab-b/laboratory").json()["team"] == []
    assert client.get("/labs/ufmg/laboratory").json()["team"] == ABOUT["team"]
