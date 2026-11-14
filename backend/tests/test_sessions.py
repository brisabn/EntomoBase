import re

import jwt
import pytest

import mailer
import models
import settings
from conftest import EMAIL, PASSWORD, make_token

SITE = "https://entomobase.example"
NEW_PASSWORD = "a-brand-new-password"


@pytest.fixture(autouse=True)
def mail_in_memory(monkeypatch):
    monkeypatch.setenv("MAIL_BACKEND", "memory")
    monkeypatch.setenv("SITE_URL", SITE)
    monkeypatch.delenv("ENTOMOBASE_ENV", raising=False)
    mailer.outbox.clear()


def sign_in(client, password=PASSWORD):
    response = client.post("/login", json={"email": EMAIL, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def works(client, headers):
    return client.get("/me", headers=headers).status_code == 200


def refused_as_expired(client, headers):
    response = client.get("/me", headers=headers)
    return (response.status_code, response.json()["detail"]["code"]) == (401, "session_expired")


def change_password(client, headers, current=PASSWORD, new=NEW_PASSWORD):
    return client.put("/me/password", json={"current_password": current, "new_password": new}, headers=headers)


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- the version inside the token ----------
def test_the_login_token_carries_the_version_of_the_account(client, user, db):
    headers = sign_in(client)
    claims = jwt.decode(headers["Authorization"].split()[1], settings.SECRET_KEY, algorithms=["HS256"])
    assert claims["ver"] == 0 == db.query(models.User).one().session_version


def test_a_token_from_before_versions_existed_still_works_until_the_sessions_end(client, user, db):
    # make_token writes no version, like the tokens given before this change
    old = bearer(make_token())
    assert works(client, old)
    assert change_password(client, old).status_code == 200
    assert refused_as_expired(client, old)


def test_a_token_with_another_version_is_refused(client, user):
    for version in (1, -1, "0"):
        forged = jwt.encode({"sub": EMAIL, "exp": 9_999_999_999, "ver": version}, settings.SECRET_KEY, algorithm="HS256")
        assert refused_as_expired(client, bearer(forged)), version


# ---------- changing the password on the account page ----------
def test_changing_the_password_signs_out_the_other_devices_and_keeps_this_one(client, user):
    laptop, phone = sign_in(client), sign_in(client)
    response = change_password(client, laptop)
    assert response.status_code == 200, response.text
    assert refused_as_expired(client, phone)
    # the token used for the change is old too; the answer brings the one that goes on working here
    assert refused_as_expired(client, laptop)
    assert works(client, bearer(response.json()["access_token"]))


def test_a_wrong_current_password_ends_nothing(client, user):
    laptop, phone = sign_in(client), sign_in(client)
    assert change_password(client, laptop, current="not-the-password").status_code == 400
    assert works(client, phone) and works(client, laptop)


def test_a_weak_new_password_ends_nothing(client, user):
    laptop, phone = sign_in(client), sign_in(client)
    assert change_password(client, laptop, new="short").status_code == 400
    assert works(client, phone)


def test_the_new_password_signs_in_again_after_the_sessions_ended(client, user):
    change_password(client, sign_in(client))
    assert works(client, sign_in(client, NEW_PASSWORD))


# ---------- choosing a new password by the e-mail link ----------
def test_a_new_password_by_e_mail_signs_out_every_device(client, user):
    laptop = sign_in(client)
    client.post("/forgot-password", json={"email": EMAIL})
    code = re.search(r"/#/new-password/([\w-]+)", mailer.outbox[-1].get_content()).group(1)
    response = client.post("/reset-password", json={"code": code, "password": NEW_PASSWORD})
    assert response.status_code == 200, response.text
    assert "access_token" not in response.json()
    assert refused_as_expired(client, laptop)
    assert works(client, sign_in(client, NEW_PASSWORD))


def test_only_asking_for_a_link_ends_nothing(client, user):
    laptop = sign_in(client)
    client.post("/forgot-password", json={"email": EMAIL})
    assert works(client, laptop)


# ---------- signing out of the other devices ----------
def test_signing_out_of_the_other_devices(client, user):
    laptop, phone = sign_in(client), sign_in(client)
    response = client.post("/me/sessions/end-others", headers=laptop)
    assert response.status_code == 200, response.text
    here = bearer(response.json()["access_token"])
    assert refused_as_expired(client, phone) and refused_as_expired(client, laptop)
    assert works(client, here)
    # again, from the device that stayed
    again = bearer(client.post("/me/sessions/end-others", headers=here).json()["access_token"])
    assert refused_as_expired(client, here) and works(client, again)


def test_signing_out_of_the_other_devices_needs_a_session(client, user):
    assert client.post("/me/sessions/end-others").status_code == 401


def test_the_sessions_of_one_account_do_not_touch_another(client, user, researcher):
    client.post("/me/sessions/end-others", headers=sign_in(client))
    assert works(client, researcher)


def test_an_ended_session_reaches_nothing_of_the_laboratory(client, user):
    laptop = sign_in(client)
    client.post("/me/sessions/end-others", headers=sign_in(client))
    response = client.get("/labs/ufmg/members", headers=laptop)
    assert (response.status_code, response.json()["detail"]["code"]) == (401, "session_expired")
