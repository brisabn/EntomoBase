import pytest

import models
from conftest import EMAIL, RESEARCHER_EMAIL, add_user, make_token


def second_lab(db):
    lab = models.Laboratory(slug="lab-b", name="Lab B", institution="B", collection_code="B", license="x", listed=True)
    db.add(lab)
    db.commit()
    return lab


def join(db, email, lab, role):
    user = db.query(models.User).filter_by(email=email).one()
    db.add(models.Membership(user_id=user.id, laboratory_id=lab.id, role=role))
    db.commit()


# ---------- listing ----------
def test_an_admin_sees_the_members_of_the_laboratory(client, admin, researcher):
    response = client.get("/labs/ufmg/members", headers=admin)
    assert response.status_code == 200
    members = response.json()
    assert [(m["email"], m["role"]) for m in members] == [(EMAIL, "admin"), (RESEARCHER_EMAIL, "researcher")]
    assert all(isinstance(m["id"], int) and m["name"] is None for m in members)


def test_the_list_is_ordered_by_email(client, admin, password_hash, db):
    for email in ("zed@lab.br", "amy@lab.br", "mia@lab.br"):
        add_user(email, password_hash, role="researcher")
    emails = [m["email"] for m in client.get("/labs/ufmg/members", headers=admin).json()]
    assert emails == sorted(emails)


def test_the_name_is_shown_when_there_is_one(client, admin, db):
    db.query(models.User).update({"name": "Ana Admin"})
    db.commit()
    assert client.get("/labs/ufmg/members", headers=admin).json()[0]["name"] == "Ana Admin"


def test_the_list_never_has_passwords_or_other_private_fields(client, admin, researcher):
    response = client.get("/labs/ufmg/members", headers=admin)
    assert set(response.json()[0]) == {"id", "email", "name", "role"}
    assert "argon2" not in response.text and "password" not in response.text


def test_only_the_members_of_this_laboratory_are_listed(client, admin, password_hash, db):
    other = second_lab(db)
    add_user("elsewhere@lab.br", password_hash)
    join(db, "elsewhere@lab.br", other, "researcher")
    assert [m["email"] for m in client.get("/labs/ufmg/members", headers=admin).json()] == [EMAIL]
    assert "elsewhere" not in client.get("/labs/ufmg/members", headers=admin).text


def test_a_user_of_two_laboratories_appears_in_each_with_the_role_there(client, admin, db):
    other = second_lab(db)
    join(db, EMAIL, other, "researcher")
    # an admin here, but only a researcher in the other one, which they cannot list
    assert client.get("/labs/ufmg/members", headers=admin).json()[0]["role"] == "admin"
    assert client.get("/labs/lab-b/members", headers=admin).status_code == 403


# ---------- who may list ----------
def test_a_researcher_cannot_list_the_members(client, researcher):
    response = client.get("/labs/ufmg/members", headers=researcher)
    assert response.status_code == 403 and response.json()["detail"]["code"] == "forbidden"


def test_someone_who_is_not_a_member_cannot_list_the_members(client, outsider, admin):
    assert client.get("/labs/ufmg/members", headers=outsider).status_code == 403


def test_a_visitor_cannot_list_the_members(client, admin):
    response = client.get("/labs/ufmg/members")
    assert response.status_code == 401 and response.json()["detail"]["code"] == "missing_token"


def test_a_bad_token_cannot_list_the_members(client, admin):
    response = client.get("/labs/ufmg/members", headers={"Authorization": "Bearer garbage"})
    assert response.status_code == 401 and response.json()["detail"]["code"] == "session_expired"


def test_a_platform_administrator_without_a_membership_cannot_list_the_members(client, superadmin, admin):
    assert client.get("/labs/ufmg/members", headers=superadmin).status_code == 403


def test_the_admin_of_another_laboratory_cannot_list_these_members(client, admin, password_hash, db):
    other = second_lab(db)
    add_user("boss@lab.br", password_hash)
    join(db, "boss@lab.br", other, "admin")
    headers = {"Authorization": f"Bearer {make_token(email='boss@lab.br')}"}
    assert client.get("/labs/ufmg/members", headers=headers).status_code == 403
    assert client.get("/labs/lab-b/members", headers=headers).status_code == 200


def test_an_unknown_laboratory_is_a_404(client, admin):
    response = client.get("/labs/nope/members", headers=admin)
    assert response.status_code == 404 and response.json()["detail"]["code"] == "lab_not_found"


def test_losing_the_admin_role_takes_effect_at_once(client, admin, db):
    assert client.get("/labs/ufmg/members", headers=admin).status_code == 200
    db.query(models.Membership).update({"role": "researcher"})
    db.commit()
    assert client.get("/labs/ufmg/members", headers=admin).status_code == 403


# the members have no address without the laboratory: there is no "old" /members
def test_there_is_no_address_without_the_laboratory(client, admin):
    assert client.get("/members", headers=admin).status_code == 404


def test_a_new_laboratory_lists_its_first_admin(client, superadmin, user, admin):
    body = {"slug": "fresh", "name": "Fresh", "institution": "F", "collection_code": "F", "admin_email": EMAIL}
    client.post("/labs", json=body, headers=superadmin)
    assert [(m["email"], m["role"]) for m in client.get("/labs/fresh/members", headers=admin).json()] == [(EMAIL, "admin")]

