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



# ---------- changing a role ----------
def member_id(db, email, slug="ufmg"):
    return db.query(models.Membership).join(models.User).join(models.Laboratory).filter(
        models.User.email == email, models.Laboratory.slug == slug
    ).one().id


def role_of(db, email, slug="ufmg"):
    db.expire_all()
    return db.get(models.Membership, member_id(db, email, slug)).role


def test_an_admin_promotes_a_researcher(client, admin, researcher, db):
    response = client.put(f"/labs/ufmg/members/{member_id(db, RESEARCHER_EMAIL)}", json={"role": "admin"}, headers=admin)
    assert response.status_code == 200
    assert response.json() == {"id": member_id(db, RESEARCHER_EMAIL), "email": RESEARCHER_EMAIL, "name": None, "role": "admin"}
    assert role_of(db, RESEARCHER_EMAIL) == "admin"


def test_the_promoted_person_can_now_manage_members(client, admin, researcher, db):
    assert client.get("/labs/ufmg/members", headers=researcher).status_code == 403
    client.put(f"/labs/ufmg/members/{member_id(db, RESEARCHER_EMAIL)}", json={"role": "admin"}, headers=admin)
    assert client.get("/labs/ufmg/members", headers=researcher).status_code == 200


def test_an_admin_demotes_another_admin_when_there_is_a_second_one(client, admin, researcher, db):
    client.put(f"/labs/ufmg/members/{member_id(db, RESEARCHER_EMAIL)}", json={"role": "admin"}, headers=admin)
    response = client.put(f"/labs/ufmg/members/{member_id(db, RESEARCHER_EMAIL)}", json={"role": "researcher"}, headers=admin)
    assert response.status_code == 200 and role_of(db, RESEARCHER_EMAIL) == "researcher"


def test_an_admin_can_demote_themselves_when_another_admin_exists(client, admin, researcher, db):
    client.put(f"/labs/ufmg/members/{member_id(db, RESEARCHER_EMAIL)}", json={"role": "admin"}, headers=admin)
    response = client.put(f"/labs/ufmg/members/{member_id(db, EMAIL)}", json={"role": "researcher"}, headers=admin)
    assert response.status_code == 200 and role_of(db, EMAIL) == "researcher"


def test_the_last_admin_cannot_be_demoted(client, admin, researcher, db):
    response = client.put(f"/labs/ufmg/members/{member_id(db, EMAIL)}", json={"role": "researcher"}, headers=admin)
    assert response.status_code == 400 and response.json()["detail"]["code"] == "last_admin"
    assert role_of(db, EMAIL) == "admin"


def test_the_last_admin_is_counted_per_laboratory(client, admin, db):
    other = second_lab(db)
    join(db, EMAIL, other, "admin")
    # being an admin of another laboratory too does not make this the "second" admin here
    response = client.put(f"/labs/ufmg/members/{member_id(db, EMAIL)}", json={"role": "researcher"}, headers=admin)
    assert response.status_code == 400 and response.json()["detail"]["code"] == "last_admin"


def test_keeping_the_same_role_is_fine_even_for_the_last_admin(client, admin, db):
    response = client.put(f"/labs/ufmg/members/{member_id(db, EMAIL)}", json={"role": "admin"}, headers=admin)
    assert response.status_code == 200 and response.json()["role"] == "admin"


def test_a_researcher_cannot_change_roles_not_even_their_own(client, admin, researcher, db):
    for headers in (researcher,):
        response = client.put(f"/labs/ufmg/members/{member_id(db, RESEARCHER_EMAIL)}", json={"role": "admin"}, headers=headers)
        assert response.status_code == 403
    assert role_of(db, RESEARCHER_EMAIL) == "researcher"


def test_someone_who_is_not_a_member_cannot_change_roles(client, admin, outsider, db):
    response = client.put(f"/labs/ufmg/members/{member_id(db, EMAIL)}", json={"role": "researcher"}, headers=outsider)
    assert response.status_code == 403 and role_of(db, EMAIL) == "admin"


def test_a_visitor_cannot_change_roles(client, admin, db):
    response = client.put(f"/labs/ufmg/members/{member_id(db, EMAIL)}", json={"role": "researcher"})
    assert response.status_code == 401


def test_a_platform_administrator_without_a_membership_cannot_change_roles(client, superadmin, admin, researcher, db):
    response = client.put(f"/labs/ufmg/members/{member_id(db, RESEARCHER_EMAIL)}", json={"role": "admin"}, headers=superadmin)
    assert response.status_code == 403 and role_of(db, RESEARCHER_EMAIL) == "researcher"


def test_the_member_of_another_laboratory_is_a_404_not_a_change(client, admin, password_hash, db):
    other = second_lab(db)
    add_user("elsewhere@lab.br", password_hash)
    join(db, "elsewhere@lab.br", other, "researcher")
    other_id = member_id(db, "elsewhere@lab.br", "lab-b")
    response = client.put(f"/labs/ufmg/members/{other_id}", json={"role": "admin"}, headers=admin)
    assert response.status_code == 404 and response.json()["detail"]["code"] == "member_not_found"
    assert role_of(db, "elsewhere@lab.br", "lab-b") == "researcher"


def test_an_admin_of_one_laboratory_cannot_change_roles_in_another(client, admin, password_hash, db):
    other = second_lab(db)
    add_user("elsewhere@lab.br", password_hash)
    join(db, "elsewhere@lab.br", other, "researcher")
    response = client.put(f"/labs/lab-b/members/{member_id(db, 'elsewhere@lab.br', 'lab-b')}", json={"role": "admin"}, headers=admin)
    assert response.status_code == 403
    assert role_of(db, "elsewhere@lab.br", "lab-b") == "researcher"


def test_an_unknown_member_is_a_404(client, admin):
    response = client.put("/labs/ufmg/members/99999", json={"role": "admin"}, headers=admin)
    assert response.status_code == 404 and response.json()["detail"]["code"] == "member_not_found"


@pytest.mark.parametrize("body", [{"role": "owner"}, {"role": ""}, {"role": None}, {}, {"role": "ADMIN"}])
def test_only_the_two_roles_are_accepted(client, admin, researcher, db, body):
    response = client.put(f"/labs/ufmg/members/{member_id(db, RESEARCHER_EMAIL)}", json=body, headers=admin)
    assert response.status_code == 422
    assert role_of(db, RESEARCHER_EMAIL) == "researcher"


def test_a_member_cannot_be_given_a_different_user_or_laboratory_through_the_body(client, admin, researcher, db):
    other = second_lab(db)
    before = db.get(models.Membership, member_id(db, RESEARCHER_EMAIL))
    user_id = before.user_id
    client.put(f"/labs/ufmg/members/{before.id}", json={"role": "admin", "laboratory_id": other.id, "user_id": 999}, headers=admin)
    db.expire_all()
    after = db.get(models.Membership, before.id)
    assert (after.user_id, after.laboratory_id) == (user_id, before.laboratory_id)


def test_there_is_no_address_for_roles_without_the_laboratory(client, admin, db):
    assert client.put(f"/members/{member_id(db, EMAIL)}", json={"role": "admin"}, headers=admin).status_code == 404


# ---------- removing a member ----------
def test_an_admin_removes_a_researcher(client, admin, researcher, db):
    response = client.delete(f"/labs/ufmg/members/{member_id(db, RESEARCHER_EMAIL)}", headers=admin)
    assert response.status_code == 204 and response.content == b""
    assert [m["email"] for m in client.get("/labs/ufmg/members", headers=admin).json()] == [EMAIL]


def test_the_removed_person_loses_access_at_once(client, admin, researcher, db):
    from helpers import project_body
    assert client.post("/labs/ufmg/projects", json=project_body(), headers=researcher).status_code == 201
    client.delete(f"/labs/ufmg/members/{member_id(db, RESEARCHER_EMAIL)}", headers=admin)
    assert client.post("/labs/ufmg/projects", json=project_body(), headers=researcher).status_code == 403
    assert client.get("/labs/ufmg/export/csv?full=true", headers=researcher).status_code == 403


def test_removing_keeps_the_account_and_the_work_they_did(client, admin, researcher, db):
    from helpers import create_project
    create_project(client, researcher, title="Made by the researcher")
    client.delete(f"/labs/ufmg/members/{member_id(db, RESEARCHER_EMAIL)}", headers=admin)
    assert db.query(models.User).filter_by(email=RESEARCHER_EMAIL).count() == 1
    assert [p["title"] for p in client.get("/labs/ufmg/projects", headers=admin).json()] == ["Made by the researcher"]


def test_removing_from_one_laboratory_keeps_the_membership_in_another(client, admin, researcher, db):
    other = second_lab(db)
    join(db, RESEARCHER_EMAIL, other, "researcher")
    client.delete(f"/labs/ufmg/members/{member_id(db, RESEARCHER_EMAIL)}", headers=admin)
    assert role_of(db, RESEARCHER_EMAIL, "lab-b") == "researcher"


def test_an_admin_can_remove_another_admin_when_there_is_a_second_one(client, admin, researcher, db):
    client.put(f"/labs/ufmg/members/{member_id(db, RESEARCHER_EMAIL)}", json={"role": "admin"}, headers=admin)
    assert client.delete(f"/labs/ufmg/members/{member_id(db, RESEARCHER_EMAIL)}", headers=admin).status_code == 204


def test_an_admin_can_leave_when_another_admin_exists(client, admin, researcher, db):
    client.put(f"/labs/ufmg/members/{member_id(db, RESEARCHER_EMAIL)}", json={"role": "admin"}, headers=admin)
    assert client.delete(f"/labs/ufmg/members/{member_id(db, EMAIL)}", headers=admin).status_code == 204
    assert client.get("/labs/ufmg/members", headers=admin).status_code == 403


def test_the_last_admin_cannot_be_removed(client, admin, researcher, db):
    response = client.delete(f"/labs/ufmg/members/{member_id(db, EMAIL)}", headers=admin)
    assert response.status_code == 400 and response.json()["detail"]["code"] == "last_admin"
    assert role_of(db, EMAIL) == "admin"


def test_the_last_admin_is_counted_per_laboratory_when_removing(client, admin, db):
    other = second_lab(db)
    join(db, EMAIL, other, "admin")
    response = client.delete(f"/labs/ufmg/members/{member_id(db, EMAIL)}", headers=admin)
    assert response.status_code == 400 and response.json()["detail"]["code"] == "last_admin"


def test_a_researcher_cannot_remove_anyone_not_even_themselves(client, admin, researcher, db):
    for email in (EMAIL, RESEARCHER_EMAIL):
        assert client.delete(f"/labs/ufmg/members/{member_id(db, email)}", headers=researcher).status_code == 403
    assert db.query(models.Membership).count() == 2


def test_someone_who_is_not_a_member_cannot_remove_anyone(client, admin, outsider, db):
    assert client.delete(f"/labs/ufmg/members/{member_id(db, EMAIL)}", headers=outsider).status_code == 403
    assert db.query(models.Membership).count() == 1


def test_a_visitor_cannot_remove_anyone(client, admin, db):
    assert client.delete(f"/labs/ufmg/members/{member_id(db, EMAIL)}").status_code == 401
    assert db.query(models.Membership).count() == 1


def test_a_platform_administrator_without_a_membership_cannot_remove_anyone(client, superadmin, admin, researcher, db):
    assert client.delete(f"/labs/ufmg/members/{member_id(db, RESEARCHER_EMAIL)}", headers=superadmin).status_code == 403
    assert db.query(models.Membership).count() == 2


def test_a_member_of_another_laboratory_is_a_404_and_stays(client, admin, password_hash, db):
    other = second_lab(db)
    add_user("elsewhere@lab.br", password_hash)
    join(db, "elsewhere@lab.br", other, "researcher")
    response = client.delete(f"/labs/ufmg/members/{member_id(db, 'elsewhere@lab.br', 'lab-b')}", headers=admin)
    assert response.status_code == 404 and response.json()["detail"]["code"] == "member_not_found"
    assert role_of(db, "elsewhere@lab.br", "lab-b") == "researcher"


def test_an_admin_cannot_remove_people_from_a_laboratory_they_do_not_manage(client, admin, password_hash, db):
    other = second_lab(db)
    add_user("elsewhere@lab.br", password_hash)
    join(db, "elsewhere@lab.br", other, "researcher")
    response = client.delete(f"/labs/lab-b/members/{member_id(db, 'elsewhere@lab.br', 'lab-b')}", headers=admin)
    assert response.status_code == 403 and db.query(models.Membership).count() == 2


def test_removing_an_unknown_member_is_a_404(client, admin):
    response = client.delete("/labs/ufmg/members/99999", headers=admin)
    assert response.status_code == 404 and response.json()["detail"]["code"] == "member_not_found"


def test_removing_the_same_member_twice_is_a_404_the_second_time(client, admin, researcher, db):
    target = member_id(db, RESEARCHER_EMAIL)
    assert client.delete(f"/labs/ufmg/members/{target}", headers=admin).status_code == 204
    assert client.delete(f"/labs/ufmg/members/{target}", headers=admin).status_code == 404


def test_there_is_no_address_for_removing_without_the_laboratory(client, admin, researcher, db):
    assert client.delete(f"/members/{member_id(db, RESEARCHER_EMAIL)}", headers=admin).status_code == 404
    assert db.query(models.Membership).count() == 2


# ---------- leaving on one's own ----------
def leave(client, headers, slug="ufmg", **kwargs):
    return client.request("DELETE", f"/labs/{slug}/membership", headers=headers, **kwargs)


def test_a_researcher_leaves_the_laboratory(client, admin, researcher, db):
    response = leave(client, researcher)
    assert response.status_code == 204 and response.content == b""
    assert [m["email"] for m in client.get("/labs/ufmg/members", headers=admin).json()] == [EMAIL]


def test_whoever_left_loses_access_at_once_and_keeps_the_account_and_the_work(client, admin, researcher, db):
    from helpers import create_project, project_body
    create_project(client, researcher, title="Made by the researcher", visibility="private")
    leave(client, researcher)
    assert client.post("/labs/ufmg/projects", json=project_body(), headers=researcher).status_code == 403
    assert client.get("/labs/ufmg/projects", headers=researcher).json() == []
    assert db.query(models.User).filter_by(email=RESEARCHER_EMAIL).count() == 1
    assert [p["title"] for p in client.get("/labs/ufmg/projects", headers=admin).json()] == ["Made by the researcher"]


def test_an_admin_leaves_when_another_admin_stays(client, admin, researcher, db):
    client.put(f"/labs/ufmg/members/{member_id(db, RESEARCHER_EMAIL)}", json={"role": "admin"}, headers=admin)
    assert leave(client, admin).status_code == 204
    assert client.get("/labs/ufmg/members", headers=admin).status_code == 403
    assert role_of(db, RESEARCHER_EMAIL) == "admin"


def test_the_last_admin_cannot_leave(client, admin, researcher, db):
    response = leave(client, admin)
    assert response.status_code == 400 and response.json()["detail"]["code"] == "last_admin"
    assert role_of(db, EMAIL) == "admin"


def test_being_an_admin_elsewhere_does_not_let_the_last_admin_here_leave(client, admin, db):
    join(db, EMAIL, second_lab(db), "admin")
    assert leave(client, admin).json()["detail"]["code"] == "last_admin"


def test_leaving_one_laboratory_keeps_the_others(client, admin, researcher, db):
    join(db, RESEARCHER_EMAIL, second_lab(db), "researcher")
    leave(client, researcher)
    assert role_of(db, RESEARCHER_EMAIL, "lab-b") == "researcher"
    assert db.query(models.Membership).join(models.User).filter(models.User.email == RESEARCHER_EMAIL).count() == 1


def test_leaving_another_laboratory_only_touches_that_one(client, admin, researcher, db):
    join(db, RESEARCHER_EMAIL, second_lab(db), "researcher")
    assert leave(client, researcher, slug="lab-b").status_code == 204
    assert role_of(db, RESEARCHER_EMAIL) == "researcher"


def test_nobody_else_can_be_made_to_leave_through_the_body(client, admin, researcher, db):
    before = member_id(db, RESEARCHER_EMAIL)
    client.put(f"/labs/ufmg/members/{before}", json={"role": "admin"}, headers=admin)
    leave(client, admin, json={"user_id": db.query(models.User).filter_by(email=RESEARCHER_EMAIL).one().id, "member_id": before})
    assert role_of(db, RESEARCHER_EMAIL) == "admin"
    assert db.query(models.Membership).join(models.User).filter(models.User.email == EMAIL).count() == 0


def test_only_members_can_leave(client, admin, outsider, superadmin, db):
    assert leave(client, outsider).status_code == 403
    assert leave(client, superadmin).status_code == 403
    assert leave(client, {}).status_code == 401
    assert db.query(models.Membership).count() == 1


def test_leaving_twice_is_refused_the_second_time(client, admin, researcher):
    assert leave(client, researcher).status_code == 204
    assert leave(client, researcher).status_code == 403


def test_there_is_no_address_for_leaving_without_the_laboratory(client, admin, researcher, db):
    assert client.delete("/membership", headers=researcher).status_code in (404, 405)
    assert db.query(models.Membership).count() == 2


def test_the_invitations_of_an_admin_who_left_stop_working(client, admin, researcher, db, monkeypatch):
    import re
    import mailer
    monkeypatch.setenv("MAIL_BACKEND", "memory")
    monkeypatch.setenv("SITE_URL", "https://entomobase.example")
    mailer.outbox.clear()
    client.put(f"/labs/ufmg/members/{member_id(db, RESEARCHER_EMAIL)}", json={"role": "admin"}, headers=admin)
    client.post("/labs/ufmg/invitations", json={"email": "invited@lab.br"}, headers=researcher)
    code = re.search(r"/#/invite/([\w-]+)", mailer.outbox[0].get_content()).group(1)
    leave(client, researcher)
    assert client.get(f"/invitations/{code}").status_code == 404


# ---------- adding a member ----------
# there is no way to put someone into a laboratory directly any more: an admin invites them by e-mail and
# they accept (test_invitations.py). The old route answered whether an address had an account
def test_there_is_no_route_that_adds_a_member_directly(client, admin, password_hash, db):
    add_user("new@lab.br", password_hash)
    for url in ("/labs/ufmg/members", "/members"):
        assert client.post(url, json={"email": "new@lab.br", "role": "admin"}, headers=admin).status_code in (404, 405)
    assert db.query(models.Membership).count() == 1
