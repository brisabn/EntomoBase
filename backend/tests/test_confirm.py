import re
from datetime import datetime, timedelta

import pytest

import email_confirmation
import mailer
import models
from conftest import EMAIL, PASSWORD, add_user

NEW = {"email": "new.person@lab.br", "password": "a-good-password", "name": "New Person"}


@pytest.fixture(autouse=True)
def mail_in_memory(monkeypatch):
    monkeypatch.setenv("MAIL_BACKEND", "memory")
    monkeypatch.setenv("SITE_URL", "https://entomobase.example")
    mailer.outbox.clear()


def sign_up(client, **changes):
    assert client.post("/signup", json={**NEW, **changes}).status_code == 202
    return re.search(r"/#/confirm/([\w-]+)", mailer.outbox[-1].get_content()).group(1)


def confirm(client, code):
    return client.post("/confirm", json={"code": code})


def log_in(client, email=NEW["email"], password=NEW["password"]):
    return client.post("/login", json={"email": email, "password": password})


# ---------- confirming ----------
def test_the_code_from_the_e_mail_confirms_the_address(client, db):
    response = confirm(client, sign_up(client))
    assert response.status_code == 200 and response.json() == {"status": "confirmed", "email": NEW["email"]}
    moment = db.query(models.User).one().email_verified_at
    assert moment is not None and abs(email_confirmation.utc_now() - moment) < timedelta(seconds=30)


def test_confirming_gives_no_session(client):
    assert "access_token" not in confirm(client, sign_up(client)).json()


def test_after_confirming_the_person_can_sign_in(client):
    code = sign_up(client)
    assert log_in(client).status_code == 403
    confirm(client, code)
    response = log_in(client)
    assert response.status_code == 200 and response.json()["email"] == NEW["email"]


def test_a_code_works_only_once(client):
    code = sign_up(client)
    assert confirm(client, code).status_code == 200
    response = confirm(client, code)
    assert response.status_code == 400 and response.json()["detail"]["code"] == "invalid_code"


def test_confirming_removes_every_code_of_that_person_only(client, db):
    sign_up(client, email="other@lab.br")
    code = sign_up(client)
    confirm(client, code)
    assert [row.user.email for row in db.query(models.EmailConfirmation).all()] == ["other@lab.br"]


def test_an_older_code_stops_working_when_a_new_one_is_sent(client):
    old = sign_up(client)
    new = sign_up(client)
    assert confirm(client, old).status_code == 400
    assert confirm(client, new).status_code == 200


def test_an_expired_code_is_refused(client, db):
    code = sign_up(client)
    row = db.query(models.EmailConfirmation).one()
    row.expires_at = email_confirmation.utc_now() - timedelta(seconds=1)
    db.commit()
    assert confirm(client, code).json()["detail"]["code"] == "invalid_code"
    db.expire_all()
    assert db.query(models.User).one().email_verified_at is None


def test_a_code_about_to_expire_still_works(client, db):
    code = sign_up(client)
    db.query(models.EmailConfirmation).one().expires_at = email_confirmation.utc_now() + timedelta(seconds=30)
    db.commit()
    assert confirm(client, code).status_code == 200


@pytest.mark.parametrize("code", ["made-up", "x" * 43, email_confirmation.hash_code("anything")])
def test_an_unknown_code_is_refused(client, db, code):
    sign_up(client)
    response = confirm(client, code)
    assert response.status_code == 400 and response.json()["detail"]["code"] == "invalid_code"
    assert db.query(models.User).one().email_verified_at is None


def test_the_stored_hash_is_not_a_code(client, db):
    sign_up(client)
    stored = db.query(models.EmailConfirmation).one().code_hash
    assert confirm(client, stored).status_code == 400


@pytest.mark.parametrize("body", [{}, {"code": ""}, {"code": "x" * 101}])
def test_a_missing_or_oversized_code_is_a_422(client, body):
    assert client.post("/confirm", json=body).status_code == 422


def test_an_earlier_confirmation_date_is_kept(client, db):
    add_user(NEW["email"], "x")
    user = db.query(models.User).one()
    email_confirmation.issue_code(db, user)
    db.commit()
    code = email_confirmation.new_code()
    db.query(models.EmailConfirmation).one().code_hash = email_confirmation.hash_code(code)
    db.commit()
    assert confirm(client, code).status_code == 200
    db.expire_all()
    assert db.query(models.User).one().email_verified_at == datetime(2026, 1, 1)


def test_there_is_no_confirmation_inside_a_laboratory(client):
    assert client.post("/labs/ufmg/confirm", json={"code": sign_up(client)}).status_code == 404


# ---------- signing in before confirming ----------
def test_an_unconfirmed_account_cannot_sign_in(client):
    sign_up(client)
    response = log_in(client)
    assert response.status_code == 403 and response.json()["detail"]["code"] == "email_not_confirmed"
    assert "access_token" not in response.text


def test_a_wrong_password_on_an_unconfirmed_account_is_just_a_wrong_password(client):
    sign_up(client)
    response = log_in(client, password="wrong-password")
    assert response.status_code == 401 and response.json()["detail"]["code"] == "invalid_credentials"


def test_someone_who_took_an_address_first_never_gets_a_session(client):
    sign_up(client, password="squatter-password")
    assert log_in(client, password="squatter-password").status_code == 403
    confirm(client, sign_up(client, password="owner-password-1"))
    assert log_in(client, password="squatter-password").status_code == 401
    assert log_in(client, password="owner-password-1").status_code == 200


def test_a_confirmed_account_signs_in_as_before(client, user):
    assert log_in(client, EMAIL, PASSWORD).status_code == 200
