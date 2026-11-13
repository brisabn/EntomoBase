import re
from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

import invitations
import mailer
import main
import models
from conftest import EMAIL, PASSWORD, RESEARCHER_EMAIL, add_user, make_token
from email_confirmation import hash_code, utc_now
from security import verify_password

SITE = "https://entomobase.example"
NEW = "new.person@lab.br"
ACCOUNT = {"name": "New Person", "password": "a-good-password"}


@pytest.fixture(autouse=True)
def mail_in_memory(monkeypatch):
    monkeypatch.setenv("MAIL_BACKEND", "memory")
    monkeypatch.setenv("SITE_URL", SITE + "/")
    monkeypatch.delenv("ENTOMOBASE_ENV", raising=False)
    mailer.outbox.clear()


def invite(client, headers, email=NEW, role=None, slug="ufmg"):
    body = {"email": email} if role is None else {"email": email, "role": role}
    return client.post(f"/labs/{slug}/invitations", json=body, headers=headers)


def code_in(message):
    return re.search(r"/#/invite/([\w-]+)", message.get_content()).group(1)


# invites and returns the code of the link in the e-mail
def invited(client, headers, email=NEW, role=None, slug="ufmg"):
    response = invite(client, headers, email, role, slug)
    assert response.status_code == 201, response.text
    return code_in(mailer.outbox[-1])


def accept(client, code, body=None, headers=None):
    return client.post(f"/invitations/{code}/accept", json=body, headers=headers or {})


def second_lab(db, admin_email=None):
    lab = models.Laboratory(slug="lab-b", name="Lab B", institution="B", collection_code="B", license="x", listed=True)
    db.add(lab)
    db.flush()
    if admin_email:
        user = db.query(models.User).filter_by(email=admin_email).one()
        db.add(models.Membership(user_id=user.id, laboratory_id=lab.id, role="admin"))
    db.commit()
    return lab


def role_in(db, email, slug="ufmg"):
    db.expire_all()
    membership = db.query(models.Membership).join(models.User).join(models.Laboratory).filter(
        models.User.email == email, models.Laboratory.slug == slug
    ).first()
    return membership.role if membership else None


def headers_of(email):
    return {"Authorization": f"Bearer {make_token(email=email)}"}


# ---------- sending ----------
def test_an_admin_invites_someone_and_an_e_mail_goes_out(client, admin, db):
    response = invite(client, admin)
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "email", "role", "created_at", "expires_at"}
    assert (body["email"], body["role"]) == (NEW, "researcher")
    [message] = mailer.outbox
    assert message["To"] == NEW
    assert f"{SITE}/#/invite/" in message.get_content()


def test_the_code_is_only_in_the_e_mail_and_the_database_keeps_its_hash(client, admin, db):
    response = invite(client, admin)
    code = code_in(mailer.outbox[0])
    stored = db.query(models.Invitation).one()
    assert stored.code_hash == hash_code(code) and code not in stored.code_hash
    assert code not in response.text


def test_the_invitation_works_for_seven_days(client, admin, db):
    invite(client, admin)
    stored = db.query(models.Invitation).one()
    assert stored.expires_at - stored.created_at == timedelta(days=7)
    assert abs((stored.created_at - utc_now()).total_seconds()) < 60


def test_the_e_mail_says_where_who_and_as_what_in_both_languages(client, admin, db):
    db.query(models.User).filter_by(email=EMAIL).update({"name": "Ana Admin"})
    db.commit()
    invite(client, admin, role="admin")
    text = mailer.outbox[0].get_content()
    lab_name = db.query(models.Laboratory).one().name
    assert f'"{lab_name}"' in text and "Ana Admin" in text
    assert "como administrador(a)" in text and "as admin" in text
    assert "7 dias" in text and "7 days" in text


def test_without_a_name_the_e_mail_names_the_admin_by_e_mail(client, admin):
    invite(client, admin)
    assert EMAIL in mailer.outbox[0].get_content() and "pesquisador(a)" in mailer.outbox[0].get_content()


def test_the_subject_is_fixed_whatever_the_laboratory_is_called(client, admin, db):
    db.query(models.Laboratory).update({"name": "Lab\nBcc: someone@evil.test"})
    db.commit()
    assert invite(client, admin).status_code == 201
    assert mailer.outbox[0]["Subject"] == "EntomoBase: convite para um laboratório / invitation to a laboratory"
    assert mailer.outbox[0]["Bcc"] is None


def test_the_address_is_trimmed_and_lowercased(client, admin, db):
    invite(client, admin, email="  New.Person@Lab.BR ")
    assert db.query(models.Invitation).one().email == NEW
    assert mailer.outbox[0]["To"] == NEW


@pytest.mark.parametrize("email", ["not-an-address", "two@at@lab.br", "a b@lab.br", "x@y"])
def test_an_invalid_address_is_refused_and_nothing_is_sent(client, admin, db, email):
    response = invite(client, admin, email=email)
    assert response.status_code == 400 and response.json()["detail"]["code"] == "invalid_email"
    assert mailer.outbox == [] and db.query(models.Invitation).count() == 0


@pytest.mark.parametrize("body", [{}, {"email": NEW, "role": "owner"}, {"email": "x"}, {"email": "a" * 255}])
def test_a_bad_request_is_a_422(client, admin, body):
    assert client.post("/labs/ufmg/invitations", json=body, headers=admin).status_code == 422


# the answer must not tell the admin whether the address has an account
def test_the_answer_is_the_same_with_or_without_an_account(client, admin, password_hash, db):
    add_user("has.account@lab.br", password_hash)
    add_user("unconfirmed@lab.br", password_hash, confirmed=False)
    answers = []
    for email in ("has.account@lab.br", "unconfirmed@lab.br", "nobody@lab.br"):
        response = invite(client, admin, email=email)
        body = response.json()
        answers.append((response.status_code, sorted(body), body["role"]))
    assert answers[0] == answers[1] == answers[2]
    assert len(mailer.outbox) == 3


def test_someone_already_in_the_laboratory_is_not_invited(client, admin, researcher, db):
    response = invite(client, admin, email=RESEARCHER_EMAIL)
    assert response.status_code == 400 and response.json()["detail"]["code"] == "already_member"
    assert mailer.outbox == [] and db.query(models.Invitation).count() == 0


def test_already_member_is_found_ignoring_case(client, admin, researcher, db):
    assert invite(client, admin, email=RESEARCHER_EMAIL.upper()).json()["detail"]["code"] == "already_member"


def test_a_member_of_another_laboratory_can_be_invited_here(client, admin, password_hash, db):
    lab = second_lab(db)
    add_user("elsewhere@lab.br", password_hash)
    user = db.query(models.User).filter_by(email="elsewhere@lab.br").one()
    db.add(models.Membership(user_id=user.id, laboratory_id=lab.id, role="admin"))
    db.commit()
    assert invite(client, admin, email="elsewhere@lab.br").status_code == 201


def test_inviting_again_replaces_the_invitation_and_only_the_new_link_works(client, admin, db):
    first = invited(client, admin)
    second = invited(client, admin, role="admin")
    stored = db.query(models.Invitation).one()
    assert stored.role == "admin" and stored.code_hash == hash_code(second)
    assert accept(client, first, ACCOUNT).status_code == 404
    assert accept(client, second, ACCOUNT).status_code == 200
    assert role_in(db, NEW) == "admin"


def test_inviting_again_gives_a_new_deadline(client, admin, db):
    invite(client, admin)
    db.query(models.Invitation).update({"created_at": datetime(2026, 1, 1), "expires_at": datetime(2026, 1, 2)})
    db.commit()
    invite(client, admin)
    db.expire_all()
    assert db.query(models.Invitation).one().expires_at > utc_now() + timedelta(days=6)


def test_two_laboratories_can_invite_the_same_address(client, admin, db):
    second_lab(db, admin_email=EMAIL)
    invite(client, admin)
    invite(client, admin, slug="lab-b")
    assert db.query(models.Invitation).count() == 2


def test_when_the_e_mail_cannot_be_sent_nothing_is_kept(client, admin, db, monkeypatch):
    monkeypatch.delenv("MAIL_BACKEND")
    response = invite(client, admin)
    assert response.status_code == 503 and response.json()["detail"]["code"] == "mail_unavailable"
    assert db.query(models.Invitation).count() == 0


def test_a_failed_e_mail_keeps_the_previous_invitation(client, admin, db, monkeypatch):
    code = invited(client, admin)
    monkeypatch.delenv("MAIL_BACKEND")
    invite(client, admin, role="admin")
    db.expire_all()
    stored = db.query(models.Invitation).one()
    assert stored.code_hash == hash_code(code) and stored.role == "researcher"


def test_an_invitation_created_at_the_same_moment_is_replaced(client, admin, db, monkeypatch):
    real = main.issue_invitation
    calls = []

    def first_one_loses_the_race(*args):
        calls.append(1)
        if len(calls) == 1:
            raise IntegrityError("insert", {}, Exception("unique"))
        return real(*args)

    monkeypatch.setattr(main, "issue_invitation", first_one_loses_the_race)
    assert invite(client, admin).status_code == 201
    assert len(calls) == 2 and db.query(models.Invitation).count() == 1


# ---------- the limit ----------
def test_an_admin_sends_at_most_twenty_invitations_an_hour(client, admin, db):
    for n in range(20):
        assert invite(client, admin, email=f"person{n}@lab.br").status_code == 201
    response = invite(client, admin, email="one.more@lab.br")
    assert response.status_code == 429 and response.json()["detail"]["code"] == "too_many_attempts"
    assert int(response.headers["Retry-After"]) > 0
    assert len(mailer.outbox) == 20 and db.query(models.Invitation).count() == 20


def test_the_limit_is_per_admin(client, admin, researcher, db):
    db.query(models.Membership).update({"role": "admin"})
    db.commit()
    for n in range(20):
        invite(client, admin, email=f"person{n}@lab.br")
    assert invite(client, researcher, email="other@lab.br").status_code == 201


def test_refused_invitations_do_not_count(client, admin, researcher, db):
    for _ in range(25):
        invite(client, admin, email="bad")
        invite(client, admin, email=RESEARCHER_EMAIL)
    assert invite(client, admin).status_code == 201


def test_failed_e_mails_do_not_count(client, admin, monkeypatch):
    monkeypatch.delenv("MAIL_BACKEND")
    for _ in range(25):
        invite(client, admin)
    monkeypatch.setenv("MAIL_BACKEND", "memory")
    assert invite(client, admin).status_code == 201


# ---------- who may invite, list and cancel ----------
def test_only_admins_of_the_laboratory_manage_invitations(client, admin, researcher, outsider, superadmin, db):
    code = invited(client, admin)
    invitation_id = db.query(models.Invitation).one().id
    for headers, status in ((researcher, 403), (outsider, 403), (superadmin, 403), ({}, 401)):
        assert invite(client, headers, email="x@lab.br").status_code == status
        assert client.get("/labs/ufmg/invitations", headers=headers).status_code == status
        assert client.delete(f"/labs/ufmg/invitations/{invitation_id}", headers=headers).status_code == status
    assert db.query(models.Invitation).count() == 1 and len(mailer.outbox) == 1
    assert client.get(f"/invitations/{code}").status_code == 200


def test_there_is_no_address_without_the_laboratory(client, admin):
    assert client.get("/invitations", headers=admin).status_code in (404, 405)
    assert client.post("/invitations", json={"email": NEW}, headers=admin).status_code in (404, 405)


def test_the_list_has_the_pending_invitations_of_this_laboratory_by_address(client, admin, password_hash, db):
    for email in ("zed@lab.br", "amy@lab.br"):
        invite(client, admin, email=email)
    add_user("boss@lab.br", password_hash)
    second_lab(db, admin_email="boss@lab.br")
    invite(client, headers_of("boss@lab.br"), email="only.in.b@lab.br", slug="lab-b")
    response = client.get("/labs/ufmg/invitations", headers=admin)
    assert response.status_code == 200
    assert [i["email"] for i in response.json()] == ["amy@lab.br", "zed@lab.br"]
    assert "only.in.b" not in response.text and "code" not in response.text


def test_an_admin_cancels_an_invitation_and_its_link_stops_working(client, admin, db):
    code = invited(client, admin)
    invitation_id = db.query(models.Invitation).one().id
    response = client.delete(f"/labs/ufmg/invitations/{invitation_id}", headers=admin)
    assert response.status_code == 204 and response.content == b""
    assert client.get(f"/invitations/{code}").status_code == 404
    assert client.delete(f"/labs/ufmg/invitations/{invitation_id}", headers=admin).status_code == 404


def test_an_invitation_of_another_laboratory_is_a_404_and_stays(client, admin, password_hash, db):
    add_user("boss@lab.br", password_hash)
    second_lab(db, admin_email="boss@lab.br")
    invite(client, headers_of("boss@lab.br"), slug="lab-b")
    other_id = db.query(models.Invitation).one().id
    response = client.delete(f"/labs/ufmg/invitations/{other_id}", headers=admin)
    assert response.status_code == 404 and response.json()["detail"]["code"] == "invitation_not_found"
    assert client.delete(f"/labs/lab-b/invitations/{other_id}", headers=admin).status_code == 403
    assert db.query(models.Invitation).count() == 1


# ---------- the page of the link ----------
def test_the_link_shows_the_laboratory_the_address_and_the_role(client, admin, db):
    code = invited(client, admin, role="admin")
    response = client.get(f"/invitations/{code}")
    assert response.status_code == 200
    lab = db.query(models.Laboratory).one()
    assert response.json() == {"laboratory": {"slug": lab.slug, "name": lab.name}, "email": NEW, "role": "admin", "has_account": False}


def test_the_link_says_when_the_address_has_an_account(client, admin, password_hash):
    add_user(NEW, password_hash)
    assert client.get(f"/invitations/{invited(client, admin)}").json()["has_account"] is True


def test_an_unconfirmed_account_does_not_count_as_one(client, admin, password_hash):
    add_user(NEW, password_hash, confirmed=False)
    assert client.get(f"/invitations/{invited(client, admin)}").json()["has_account"] is False


def test_an_unknown_code_is_a_404(client):
    response = client.get("/invitations/not-a-code")
    assert response.status_code == 404 and response.json()["detail"]["code"] == "invitation_not_found"


def test_an_expired_invitation_is_a_404_on_both_routes(client, admin, db):
    code = invited(client, admin)
    db.query(models.Invitation).update({"expires_at": utc_now() - timedelta(seconds=1)})
    db.commit()
    assert client.get(f"/invitations/{code}").status_code == 404
    assert accept(client, code, ACCOUNT).status_code == 404
    assert db.query(models.User).filter_by(email=NEW).count() == 0


def test_an_invitation_ends_when_whoever_sent_it_stops_being_an_admin(client, admin, researcher, db):
    db.query(models.Membership).update({"role": "admin"})
    db.commit()
    code = invited(client, researcher)
    db.query(models.Membership).filter(models.Membership.user.has(email=RESEARCHER_EMAIL)).update(
        {"role": "researcher"}, synchronize_session=False)
    db.commit()
    assert client.get(f"/invitations/{code}").status_code == 404
    assert accept(client, code, ACCOUNT).status_code == 404


def test_an_invitation_ends_when_whoever_sent_it_leaves_the_laboratory(client, admin, researcher, db):
    db.query(models.Membership).update({"role": "admin"})
    db.commit()
    code = invited(client, researcher)
    db.query(models.Membership).filter(models.Membership.user.has(email=RESEARCHER_EMAIL)).delete(synchronize_session=False)
    db.commit()
    assert accept(client, code, ACCOUNT).status_code == 404


def test_being_an_admin_of_another_laboratory_does_not_keep_an_invitation_alive(client, admin, researcher, db):
    db.query(models.Membership).update({"role": "admin"})
    db.commit()
    code = invited(client, researcher)
    second_lab(db, admin_email=RESEARCHER_EMAIL)
    db.query(models.Membership).filter(models.Membership.user.has(email=RESEARCHER_EMAIL),
                                       models.Membership.laboratory.has(slug="ufmg")).delete(synchronize_session=False)
    db.commit()
    assert client.get(f"/invitations/{code}").status_code == 404


# ---------- accepting without an account ----------
def test_accepting_creates_the_account_already_confirmed_and_in_the_laboratory(client, admin, db):
    code = invited(client, admin, role="admin")
    response = accept(client, code, ACCOUNT)
    assert response.status_code == 200
    body = response.json()
    lab = db.query(models.Laboratory).one()
    assert body["laboratory"] == {"slug": lab.slug, "name": lab.name} and body["role"] == "admin" and body["email"] == NEW
    user = db.query(models.User).filter_by(email=NEW).one()
    assert user.name == "New Person" and user.email_verified_at is not None and not user.is_superadmin
    assert verify_password(ACCOUNT["password"], user.password_hash) and ACCOUNT["password"] not in user.password_hash
    assert role_in(db, NEW) == "admin"
    assert db.query(models.Invitation).count() == 0


def test_the_new_account_is_signed_in_at_once_and_can_work(client, admin, db):
    from helpers import project_body
    token = accept(client, invited(client, admin), ACCOUNT).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/me", headers=headers).json()
    assert me["email"] == NEW and [l["role"] for l in me["laboratories"]] == ["researcher"]
    assert client.post("/labs/ufmg/projects", json=project_body(), headers=headers).status_code == 201


def test_the_new_account_signs_in_with_the_password_it_chose(client, admin):
    accept(client, invited(client, admin), ACCOUNT)
    assert client.post("/login", json={"email": NEW, "password": ACCOUNT["password"]}).status_code == 200


def test_the_address_comes_from_the_invitation_not_from_the_request(client, admin, db):
    accept(client, invited(client, admin), {**ACCOUNT, "email": "someone.else@lab.br"})
    assert [u.email for u in db.query(models.User).filter(models.User.email != EMAIL)] == [NEW]


def test_the_role_and_laboratory_come_from_the_invitation_not_from_the_request(client, admin, password_hash, db):
    add_user("boss@lab.br", password_hash)
    second_lab(db, admin_email="boss@lab.br")
    accept(client, invited(client, admin), {**ACCOUNT, "role": "admin", "laboratory_id": 2, "slug": "lab-b"})
    assert role_in(db, NEW) == "researcher" and role_in(db, NEW, "lab-b") is None


def test_the_name_is_trimmed(client, admin, db):
    accept(client, invited(client, admin), {**ACCOUNT, "name": "  Ana  "})
    assert db.query(models.User).filter_by(email=NEW).one().name == "Ana"


@pytest.mark.parametrize("body", [None, {}, {"password": "a-good-password"}, {"name": "", "password": "a-good-password"},
                                  {"name": "   ", "password": "a-good-password"}])
def test_a_new_account_needs_a_name(client, admin, db, body):
    code = invited(client, admin)
    response = accept(client, code, body)
    assert response.status_code == 400 and response.json()["detail"]["code"] == "name_required"
    assert db.query(models.User).filter_by(email=NEW).count() == 0 and db.query(models.Invitation).count() == 1


@pytest.mark.parametrize("password", [None, "", "short", "1234567"])
def test_a_new_account_needs_a_password_of_eight_characters(client, admin, db, password):
    code = invited(client, admin)
    response = accept(client, code, {"name": "Ana", "password": password})
    assert response.status_code == 400 and response.json()["detail"] == {"code": "weak_password", "params": {"minimum": 8}}
    assert db.query(models.User).filter_by(email=NEW).count() == 0 and db.query(models.Invitation).count() == 1


@pytest.mark.parametrize("body", [{"name": "a" * 121, "password": "a-good-password"}, {"name": "Ana", "password": "a" * 129}])
def test_a_name_or_password_too_long_is_a_422(client, admin, body):
    assert accept(client, invited(client, admin), body).status_code == 422


def test_a_link_works_only_once(client, admin, db):
    code = invited(client, admin)
    assert accept(client, code, ACCOUNT).status_code == 200
    again = accept(client, code, {"name": "Someone Else", "password": "another-password"})
    assert again.status_code == 404 and again.json()["detail"]["code"] == "invitation_not_found"
    assert db.query(models.User).filter_by(email=NEW).one().name == "New Person"


def test_being_signed_in_as_someone_else_does_not_change_whose_account_is_created(client, admin, researcher, db):
    accept(client, invited(client, admin), ACCOUNT, headers=researcher)
    assert role_in(db, NEW) == "researcher" and db.query(models.User).filter_by(email=NEW).count() == 1


# an address that signed up but never confirmed may have been typed by anyone; the invitation reached the
# real mailbox, so whoever accepts it takes the account over
def test_an_unconfirmed_account_is_taken_over_by_whoever_accepts(client, admin, db):
    from security import hash_password
    add_user(NEW, hash_password("the-squatters-password"), confirmed=False)
    db.query(models.User).filter_by(email=NEW).update({"name": "Squatter"})
    squatter = db.query(models.User).filter_by(email=NEW).one()
    db.add(models.EmailConfirmation(user_id=squatter.id, code_hash=hash_code("old-confirmation"),
                                    created_at=utc_now(), expires_at=utc_now() + timedelta(hours=1)))
    db.commit()
    response = accept(client, invited(client, admin), ACCOUNT)
    assert response.status_code == 200 and response.json()["access_token"]
    db.expire_all()
    user = db.query(models.User).filter_by(email=NEW).one()
    assert user.id == squatter.id and user.name == "New Person" and user.email_verified_at is not None
    assert verify_password(ACCOUNT["password"], user.password_hash)
    assert not verify_password("the-squatters-password", user.password_hash)
    assert db.query(models.EmailConfirmation).count() == 0
    assert client.post("/confirm", json={"code": "old-confirmation"}).status_code == 400


def test_two_acceptances_at_the_same_moment_create_one_account(client, admin, password_hash, db, monkeypatch):
    code = invited(client, admin)
    # the other request created the account after this one looked for it and found none
    add_user(NEW, password_hash)
    monkeypatch.setattr(main, "user_with_email", lambda db, email: None)
    response = accept(client, code, {"name": "Second", "password": "another-password"})
    assert response.status_code == 404 and response.json()["detail"]["code"] == "invitation_not_found"
    assert db.query(models.User).filter_by(email=NEW).count() == 1
    assert db.query(models.User).filter_by(email=NEW).one().password_hash == password_hash


# ---------- accepting with an account ----------
@pytest.fixture
def account(password_hash):
    add_user(NEW, password_hash)
    return headers_of(NEW)


def test_someone_with_an_account_accepts_while_signed_in(client, admin, account, db, password_hash):
    response = accept(client, invited(client, admin, role="admin"), headers=account)
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "admin" and body["email"] == NEW and body["access_token"] is None
    assert role_in(db, NEW) == "admin" and db.query(models.Invitation).count() == 0
    assert db.query(models.User).filter_by(email=NEW).one().password_hash == password_hash


def test_a_name_and_password_sent_with_an_account_change_nothing(client, admin, account, db, password_hash):
    accept(client, invited(client, admin), {"name": "Hijack", "password": "new-password-x"}, headers=account)
    user = db.query(models.User).filter_by(email=NEW).one()
    assert user.name is None and user.password_hash == password_hash


def test_with_an_account_the_link_alone_is_not_enough(client, admin, account, db):
    code = invited(client, admin)
    response = accept(client, code, ACCOUNT)
    assert response.status_code == 401 and response.json()["detail"]["code"] == "missing_token"
    bad = accept(client, code, ACCOUNT, headers={"Authorization": "Bearer garbage"})
    assert bad.status_code == 401 and bad.json()["detail"]["code"] == "session_expired"
    assert role_in(db, NEW) is None and db.query(models.Invitation).count() == 1
    assert verify_password(PASSWORD, db.query(models.User).filter_by(email=NEW).one().password_hash)


def test_another_account_cannot_accept_it(client, admin, account, researcher, db):
    code = invited(client, admin)
    response = accept(client, code, headers=researcher)
    assert response.status_code == 403 and response.json()["detail"]["code"] == "wrong_account"
    assert role_in(db, NEW) is None and db.query(models.Invitation).count() == 1
    assert accept(client, code, headers=account).status_code == 200


def test_someone_who_became_a_member_meanwhile_keeps_their_role(client, admin, account, db):
    code = invited(client, admin, role="admin")
    user = db.query(models.User).filter_by(email=NEW).one()
    db.add(models.Membership(user_id=user.id, laboratory_id=db.query(models.Laboratory).one().id, role="researcher"))
    db.commit()
    response = accept(client, code, headers=account)
    assert response.status_code == 200 and response.json()["role"] == "researcher"
    assert role_in(db, NEW) == "researcher" and db.query(models.Invitation).count() == 0
    assert db.query(models.Membership).filter(models.Membership.user.has(email=NEW)).count() == 1


def test_accepting_keeps_the_memberships_in_other_laboratories(client, admin, account, db):
    second_lab(db, admin_email=NEW)
    accept(client, invited(client, admin), headers=account)
    assert role_in(db, NEW) == "researcher" and role_in(db, NEW, "lab-b") == "admin"


def test_an_invitation_to_one_laboratory_never_adds_to_another(client, admin, account, password_hash, db):
    add_user("boss@lab.br", password_hash)
    second_lab(db, admin_email="boss@lab.br")
    accept(client, invited(client, headers_of("boss@lab.br"), slug="lab-b"), headers=account)
    assert role_in(db, NEW, "lab-b") == "researcher" and role_in(db, NEW) is None


def test_the_address_of_the_account_is_matched_ignoring_case(client, admin, password_hash, db):
    add_user("Mixed.Case@Lab.br", password_hash)
    code = invited(client, admin, email="mixed.case@lab.br")
    assert client.get(f"/invitations/{code}").json()["has_account"] is True
    assert accept(client, code, headers=headers_of("Mixed.Case@Lab.br")).status_code == 200
    assert db.query(models.User).count() == 2


def test_the_valid_days_constant_is_what_the_e_mail_says(client, admin):
    invite(client, admin)
    assert f"{invitations.INVITATION_VALID_DAYS} dias" in mailer.outbox[0].get_content()
