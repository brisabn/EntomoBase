import re
from datetime import datetime, timedelta

import pytest

import email_confirmation
import mailer
import models
from conftest import EMAIL, PASSWORD, add_user, make_token
from email_confirmation import hash_code, utc_now
from security import verify_password

SITE = "https://entomobase.example"
NEW_PASSWORD = "a-brand-new-password"


@pytest.fixture(autouse=True)
def mail_in_memory(monkeypatch):
    monkeypatch.setenv("MAIL_BACKEND", "memory")
    monkeypatch.setenv("SITE_URL", SITE + "/")
    monkeypatch.delenv("ENTOMOBASE_ENV", raising=False)
    mailer.outbox.clear()


def forgot(client, email=EMAIL):
    return client.post("/forgot-password", json={"email": email})


def code_in(message):
    return re.search(r"/#/new-password/([\w-]+)", message.get_content()).group(1)


def reset(client, code, password=NEW_PASSWORD):
    return client.post("/reset-password", json={"code": code, "password": password})


def can_sign_in(client, password, email=EMAIL):
    return client.post("/login", json={"email": email, "password": password}).status_code == 200


def stored_hash(db, email=EMAIL):
    db.expire_all()
    return db.query(models.User).filter_by(email=email).one().password_hash


# ---------- asking for a new password ----------
def test_an_account_gets_a_link_to_choose_a_new_password(client, user, db):
    response = forgot(client)
    assert response.status_code == 202 and response.json() == {"status": "reset_sent"}
    [message] = mailer.outbox
    assert message["To"] == EMAIL and f"{SITE}/#/new-password/" in message.get_content()
    stored = db.query(models.EmailConfirmation).one()
    assert stored.code_hash == hash_code(code_in(message))


def test_the_link_works_for_one_hour(client, user, db):
    forgot(client)
    stored = db.query(models.EmailConfirmation).one()
    assert stored.expires_at - stored.created_at == timedelta(hours=1)
    text = mailer.outbox[0].get_content()
    assert "1 hora" in text and "1 hour" in text


def test_the_password_does_not_change_just_by_asking(client, user, db, password_hash):
    forgot(client)
    assert stored_hash(db) == password_hash and can_sign_in(client, PASSWORD)


# the answer must not tell who has an account, and neither must the e-mail sent
def test_an_address_without_an_account_gets_the_same_answer_and_an_e_mail_saying_so(client, user, db):
    with_account = forgot(client)
    without = forgot(client, "nobody@lab.br")
    assert (with_account.status_code, with_account.json()) == (without.status_code, without.json())
    message = mailer.outbox[1]
    assert message["To"] == "nobody@lab.br" and "não há conta" in message.get_content()
    assert "/#/new-password/" not in message.get_content()
    assert db.query(models.User).count() == 1 and db.query(models.EmailConfirmation).count() == 1


def test_an_unconfirmed_account_also_gets_a_link(client, password_hash, db):
    add_user("pending@lab.br", password_hash, confirmed=False)
    forgot(client, "pending@lab.br")
    assert "/#/new-password/" in mailer.outbox[0].get_content()


def test_the_address_is_trimmed_and_matched_ignoring_case(client, user):
    forgot(client, "  ADMIN@Lab.br ")
    assert mailer.outbox[0]["To"] == EMAIL and "/#/new-password/" in mailer.outbox[0].get_content()


@pytest.mark.parametrize("email", ["not-an-address", "a b@lab.br", "x@y"])
def test_an_invalid_address_is_refused_and_nothing_is_sent(client, user, email):
    response = forgot(client, email)
    assert response.status_code == 400 and response.json()["detail"]["code"] == "invalid_email"
    assert mailer.outbox == []


@pytest.mark.parametrize("body", [{}, {"email": ""}, {"email": "a" * 255}])
def test_a_bad_request_is_a_422(client, body):
    assert client.post("/forgot-password", json=body).status_code == 422


@pytest.mark.parametrize("email", [EMAIL, "nobody@lab.br"])
def test_when_e_mail_cannot_be_sent_the_answer_is_the_same_for_everyone(client, user, db, monkeypatch, email):
    monkeypatch.delenv("MAIL_BACKEND")
    response = forgot(client, email)
    assert response.status_code == 503 and response.json()["detail"]["code"] == "mail_unavailable"
    assert db.query(models.EmailConfirmation).count() == 0


def test_asking_again_ends_the_previous_link(client, user, db):
    forgot(client)
    first = code_in(mailer.outbox[0])
    forgot(client)
    second = code_in(mailer.outbox[1])
    assert reset(client, first).json()["detail"]["code"] == "invalid_reset_code"
    assert reset(client, second).status_code == 200


def test_asking_ends_a_pending_confirmation_link(client, password_hash, db):
    add_user("pending@lab.br", password_hash, confirmed=False)
    user = db.query(models.User).filter_by(email="pending@lab.br").one()
    db.add(models.EmailConfirmation(user_id=user.id, code_hash=hash_code("old-confirmation"), created_at=utc_now(),
                                    expires_at=utc_now() + timedelta(hours=1)))
    db.commit()
    forgot(client, "pending@lab.br")
    assert client.post("/confirm", json={"code": "old-confirmation"}).status_code == 400


# ---------- the limits ----------
def test_one_address_gets_at_most_three_links_an_hour(client, user):
    for _ in range(3):
        assert forgot(client).status_code == 202
    response = forgot(client)
    assert response.status_code == 429 and response.json()["detail"]["code"] == "too_many_attempts"
    assert int(response.headers["Retry-After"]) > 0 and len(mailer.outbox) == 3


def test_one_ip_asks_at_most_five_times_an_hour(client, user):
    for n in range(5):
        assert forgot(client, f"person{n}@lab.br").status_code == 202
    assert forgot(client, "one.more@lab.br").status_code == 429
    assert len(mailer.outbox) == 5


def test_refused_addresses_do_not_count(client, user):
    for _ in range(10):
        forgot(client, "not-an-address")
    assert forgot(client).status_code == 202


# ---------- choosing the new password ----------
@pytest.fixture
def code(client, user):
    forgot(client)
    return code_in(mailer.outbox[-1])


def test_the_link_sets_the_new_password(client, code, db):
    response = reset(client, code)
    assert response.status_code == 200 and response.json() == {"status": "password_changed", "email": EMAIL}
    assert can_sign_in(client, NEW_PASSWORD) and not can_sign_in(client, PASSWORD)
    assert NEW_PASSWORD not in stored_hash(db) and verify_password(NEW_PASSWORD, stored_hash(db))


def test_the_link_works_only_once(client, code, db):
    reset(client, code)
    again = reset(client, code, "yet-another-password")
    assert again.status_code == 400 and again.json()["detail"]["code"] == "invalid_reset_code"
    assert can_sign_in(client, NEW_PASSWORD)
    assert db.query(models.EmailConfirmation).count() == 0


def test_an_expired_link_is_refused(client, code, db, password_hash):
    db.query(models.EmailConfirmation).update({"expires_at": utc_now() - timedelta(seconds=1)})
    db.commit()
    assert reset(client, code).json()["detail"]["code"] == "invalid_reset_code"
    assert stored_hash(db) == password_hash


def test_an_unknown_code_is_refused(client, user):
    response = reset(client, "not-a-code")
    assert response.status_code == 400 and response.json()["detail"]["code"] == "invalid_reset_code"


@pytest.mark.parametrize("password", ["", "short", "1234567"])
def test_the_new_password_needs_eight_characters_and_the_link_keeps_working(client, code, db, password_hash, password):
    response = reset(client, code, password)
    assert response.status_code == 400 and response.json()["detail"] == {"code": "weak_password", "params": {"minimum": 8}}
    assert stored_hash(db) == password_hash
    assert reset(client, code).status_code == 200


@pytest.mark.parametrize("body", [{}, {"code": "x"}, {"password": NEW_PASSWORD}, {"code": "x", "password": "a" * 129}, {"code": "", "password": NEW_PASSWORD}])
def test_a_bad_reset_request_is_a_422(client, body):
    assert client.post("/reset-password", json=body).status_code == 422


def test_choosing_a_password_confirms_an_unconfirmed_address(client, password_hash, db):
    add_user("pending@lab.br", password_hash, confirmed=False)
    forgot(client, "pending@lab.br")
    assert reset(client, code_in(mailer.outbox[0])).status_code == 200
    db.expire_all()
    assert db.query(models.User).filter_by(email="pending@lab.br").one().email_verified_at is not None
    assert can_sign_in(client, NEW_PASSWORD, "pending@lab.br")


def test_a_confirmed_address_keeps_its_original_date(client, code, db):
    reset(client, code)
    db.expire_all()
    assert db.query(models.User).filter_by(email=EMAIL).one().email_verified_at == datetime(2026, 1, 1)


def test_a_link_changes_only_its_own_account(client, code, password_hash, db):
    add_user("other@lab.br", password_hash)
    reset(client, code)
    assert stored_hash(db, "other@lab.br") == password_hash


def test_the_valid_hours_constant_is_what_the_e_mail_says(client, user):
    forgot(client)
    assert f"vale por {email_confirmation.RESET_VALID_HOURS} hora" in mailer.outbox[0].get_content()


# ---------- changing one's own password ----------
def change(client, headers, current=PASSWORD, new=NEW_PASSWORD):
    return client.put("/me/password", json={"current_password": current, "new_password": new}, headers=headers)


def test_a_signed_in_person_changes_their_password(client, admin, db):
    response = change(client, admin)
    assert response.status_code == 200 and response.json() == {"status": "password_changed"}
    assert can_sign_in(client, NEW_PASSWORD) and not can_sign_in(client, PASSWORD)


# a wrong current password must not sign the person out: the site does that on a 401
def test_a_wrong_current_password_is_a_400_and_changes_nothing(client, admin, db, password_hash):
    response = change(client, admin, current="not-my-password")
    assert response.status_code == 400 and response.json()["detail"]["code"] == "wrong_password"
    assert stored_hash(db) == password_hash
    assert client.get("/me", headers=admin).status_code == 200


def test_wrong_current_passwords_are_limited_like_the_login(client, admin):
    for _ in range(5):
        assert change(client, admin, current="wrong-guess").status_code == 400
    response = change(client, admin)
    assert response.status_code == 429 and response.json()["detail"]["code"] == "too_many_attempts"
    # the same counter as the login: guessing here also blocks guessing there
    assert client.post("/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 429


def test_a_right_current_password_clears_the_count(client, admin):
    for _ in range(4):
        change(client, admin, current="wrong-guess")
    assert change(client, admin, new="second-password").status_code == 200
    for _ in range(4):
        change(client, admin, current="wrong-guess")
    assert change(client, admin, current="second-password").status_code == 200


@pytest.mark.parametrize("new", ["", "short", "1234567"])
def test_the_new_password_needs_eight_characters(client, admin, db, password_hash, new):
    response = change(client, admin, new=new)
    assert response.status_code == 400 and response.json()["detail"]["code"] == "weak_password"
    assert stored_hash(db) == password_hash


def test_only_a_signed_in_person_changes_a_password(client, user, db, password_hash):
    assert change(client, {}).status_code == 401
    assert change(client, {"Authorization": "Bearer garbage"}).status_code == 401
    assert stored_hash(db) == password_hash


def test_the_password_changed_is_the_one_of_the_token(client, admin, password_hash, db):
    add_user("other@lab.br", password_hash)
    change(client, {"Authorization": f"Bearer {make_token(email='other@lab.br')}"})
    assert stored_hash(db) == password_hash and verify_password(NEW_PASSWORD, stored_hash(db, "other@lab.br"))


def test_changing_the_password_ends_a_link_sent_before(client, admin, db):
    forgot(client)
    old_link = code_in(mailer.outbox[0])
    change(client, admin)
    assert reset(client, old_link).json()["detail"]["code"] == "invalid_reset_code"
    assert can_sign_in(client, NEW_PASSWORD)


@pytest.mark.parametrize("body", [{}, {"current_password": PASSWORD}, {"new_password": NEW_PASSWORD},
                                  {"current_password": PASSWORD, "new_password": "a" * 129}])
def test_a_bad_change_request_is_a_422(client, admin, body):
    assert client.put("/me/password", json=body, headers=admin).status_code == 422
