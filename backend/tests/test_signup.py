import re
from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

import email_confirmation
import mailer
import main
import models
from conftest import EMAIL, PASSWORD, add_user
from security import verify_password

NEW = {"email": "new.person@lab.br", "password": "a-good-password", "name": "New Person"}
SITE = "https://entomobase.example"


@pytest.fixture(autouse=True)
def mail_in_memory(monkeypatch):
    monkeypatch.setenv("MAIL_BACKEND", "memory")
    monkeypatch.setenv("SITE_URL", SITE + "/")
    monkeypatch.delenv("ENTOMOBASE_ENV", raising=False)
    mailer.outbox.clear()


def sign_up(client, **changes):
    return client.post("/signup", json={**NEW, **changes})


def code_in(message):
    return re.search(r"/#/confirm/([\w-]+)", message.get_content()).group(1)


def confirm_as_user(db, email):
    from datetime import datetime
    db.query(models.User).filter_by(email=email).one().email_verified_at = datetime(2026, 1, 1)
    db.commit()


# ---------- a new account ----------
def test_signing_up_answers_202_and_creates_an_account_without_a_laboratory(client, db):
    response = sign_up(client)
    assert response.status_code == 202 and response.json() == {"status": "confirmation_sent"}
    user = db.query(models.User).one()
    assert (user.email, user.name, user.is_superadmin) == (NEW["email"], "New Person", False)
    assert user.email_verified_at is None
    assert db.query(models.Membership).count() == 0


def test_the_password_is_stored_as_a_hash(client, db):
    sign_up(client)
    stored = db.query(models.User).one().password_hash
    assert stored != NEW["password"] and verify_password(NEW["password"], stored)


def test_the_address_is_trimmed_and_lowercased_and_the_name_trimmed(client, db):
    sign_up(client, email="  New.Person@Lab.BR ", name="  Ana  ")
    user = db.query(models.User).one()
    assert (user.email, user.name) == ("new.person@lab.br", "Ana")
    assert mailer.outbox[0]["To"] == "new.person@lab.br"


def test_no_token_is_given_before_the_address_is_confirmed(client):
    assert set(sign_up(client).json()) == {"status"}


def test_the_confirmation_e_mail_has_the_link_in_both_languages(client):
    sign_up(client)
    assert len(mailer.outbox) == 1
    message = mailer.outbox[0]
    body = message.get_content()
    assert message["To"] == NEW["email"]
    assert re.search(re.escape(SITE) + r"/#/confirm/[\w-]{40,}", body)
    assert "confirme seu e-mail" in message["Subject"] and "confirm your e-mail" in message["Subject"]
    assert "Para confirmar" in body and "To confirm" in body and "24 horas" in body and "24 hours" in body


def test_only_the_hash_of_the_code_is_stored(client, db):
    sign_up(client)
    code = code_in(mailer.outbox[0])
    row = db.query(models.EmailConfirmation).one()
    assert row.code_hash == email_confirmation.hash_code(code) and code not in row.code_hash
    assert row.user_id == db.query(models.User).one().id


def test_the_code_is_valid_for_24_hours(client, db):
    sign_up(client)
    row = db.query(models.EmailConfirmation).one()
    assert row.expires_at - row.created_at == timedelta(hours=24)
    assert abs(email_confirmation.utc_now() - row.created_at) < timedelta(seconds=30)


def test_each_person_gets_a_different_code(client):
    sign_up(client)
    sign_up(client, email="other@lab.br")
    assert code_in(mailer.outbox[0]) != code_in(mailer.outbox[1])


# ---------- an address that already has a confirmed account ----------
def test_a_registered_address_gets_the_same_answer(client, user, db):
    confirm_as_user(db, EMAIL)
    new = sign_up(client)
    existing = sign_up(client, email=EMAIL)
    assert (existing.status_code, existing.json()) == (new.status_code, new.json())


def test_a_registered_address_is_left_untouched(client, user, db):
    confirm_as_user(db, EMAIL)
    before = db.query(models.User).filter_by(email=EMAIL).one().password_hash
    sign_up(client, email=EMAIL, password="another-password", name="Impostor")
    db.expire_all()
    account = db.query(models.User).filter_by(email=EMAIL).one()
    assert account.password_hash == before and account.name is None
    assert db.query(models.EmailConfirmation).count() == 0
    assert db.query(models.User).count() == 1


def test_a_registered_address_is_told_about_it_without_a_link(client, user, db):
    confirm_as_user(db, EMAIL)
    sign_up(client, email=EMAIL.upper())
    assert len(mailer.outbox) == 1
    message = mailer.outbox[0]
    assert message["To"] == EMAIL and "já tem uma conta" in message["Subject"] and "already have an account" in message["Subject"]
    assert "/#/confirm/" not in message.get_content() and SITE not in message.get_content()


def test_an_account_stored_with_capital_letters_is_still_found(client, db):
    add_user("Mixed.Case@Lab.br", "x")
    confirm_as_user(db, "Mixed.Case@Lab.br")
    sign_up(client, email="mixed.case@lab.br")
    assert db.query(models.User).count() == 1 and db.query(models.EmailConfirmation).count() == 0
    assert "already have an account" in mailer.outbox[0]["Subject"]


# ---------- an address that was never confirmed ----------
def test_the_newest_sign_up_takes_over_an_unconfirmed_account(client, db):
    sign_up(client, password="squatter-password", name="Squatter")
    sign_up(client, password="owner-password-1", name="Owner")
    db.expire_all()
    user = db.query(models.User).one()
    assert user.name == "Owner" and verify_password("owner-password-1", user.password_hash)
    assert not verify_password("squatter-password", user.password_hash)


def test_a_new_code_replaces_the_old_one(client, db):
    sign_up(client)
    first = code_in(mailer.outbox[0])
    sign_up(client)
    second = code_in(mailer.outbox[1])
    assert first != second
    assert [r.code_hash for r in db.query(models.EmailConfirmation).all()] == [email_confirmation.hash_code(second)]


def test_another_persons_code_is_not_touched(client, db):
    sign_up(client, email="one@lab.br")
    sign_up(client, email="two@lab.br")
    sign_up(client, email="one@lab.br")
    assert db.query(models.EmailConfirmation).count() == 2


# ---------- the same time whatever the address ----------
@pytest.mark.parametrize("case", ["new", "unconfirmed", "confirmed"])
def test_the_password_is_hashed_in_every_case(client, db, monkeypatch, case):
    if case != "new":
        add_user(NEW["email"], "x", confirmed=case == "confirmed")
    calls = []
    real = main.hash_password
    monkeypatch.setattr(main, "hash_password", lambda password: calls.append(password) or real(password))
    assert sign_up(client).status_code == 202
    assert calls == [NEW["password"]]


# ---------- what is refused ----------
@pytest.mark.parametrize("address", ["nobody", "a b@lab.br", "a@lab", "a@lab.br, b@lab.br", "<a@lab.br>", "a@lab.br\nBcc: x@lab.br", "\"a\"@lab.br"])
def test_an_address_that_is_not_a_plain_address_is_refused(client, db, address):
    response = sign_up(client, email=address)
    assert response.status_code == 400 and response.json()["detail"]["code"] == "invalid_email"
    assert db.query(models.User).count() == 0 and mailer.outbox == []


def test_a_short_password_is_refused_with_the_minimum(client, db):
    response = sign_up(client, password="1234567")
    assert response.status_code == 400
    assert response.json()["detail"] == {"code": "weak_password", "params": {"minimum": 8}}
    assert db.query(models.User).count() == 0 and mailer.outbox == []


def test_a_password_of_the_minimum_length_is_accepted(client):
    assert sign_up(client, password="12345678").status_code == 202


@pytest.mark.parametrize("changes", [
    {"email": None}, {"password": None}, {"name": None}, {"name": "   "}, {"name": ""}, {"email": "a@b"},
    {"password": "x" * 129}, {"name": "x" * 121}, {"email": "a" * 250 + "@lab.br"},
])
def test_an_incomplete_or_oversized_request_is_a_422(client, db, changes):
    body = {**NEW, **changes}
    body = {k: v for k, v in body.items() if v is not None}
    response = client.post("/signup", json=body)
    assert response.status_code == 422 and response.json()["detail"]["code"] == "invalid_request"
    assert db.query(models.User).count() == 0 and mailer.outbox == []


def test_the_longest_accepted_values_work(client):
    assert sign_up(client, password="x" * 128, name="n" * 120, email="a" * 60 + "@lab.br").status_code == 202


def test_there_is_no_sign_up_inside_a_laboratory(client, db):
    assert client.post("/labs/ufmg/signup", json=NEW).status_code == 404
    assert db.query(models.User).count() == 0


# ---------- when the e-mail cannot be sent ----------
def test_without_mail_configured_nothing_is_created(client, db, monkeypatch):
    monkeypatch.delenv("MAIL_BACKEND")
    response = sign_up(client)
    assert response.status_code == 503 and response.json()["detail"]["code"] == "mail_unavailable"
    assert db.query(models.User).count() == 0 and db.query(models.EmailConfirmation).count() == 0


def test_without_a_site_address_nothing_is_created(client, db, monkeypatch):
    monkeypatch.delenv("SITE_URL")
    response = sign_up(client)
    assert response.status_code == 503 and response.json()["detail"]["code"] == "mail_unavailable"
    assert db.query(models.User).count() == 0 and mailer.outbox == []


def test_a_failed_e_mail_does_not_change_an_unconfirmed_account(client, db, monkeypatch):
    sign_up(client, password="first-password-1", name="First")
    monkeypatch.delenv("MAIL_BACKEND")
    assert sign_up(client, password="second-password", name="Second").status_code == 503
    db.expire_all()
    user = db.query(models.User).one()
    assert user.name == "First" and verify_password("first-password-1", user.password_hash)
    assert db.query(models.EmailConfirmation).count() == 1


def test_a_failed_notice_to_a_registered_address_is_also_a_503(client, user, db, monkeypatch):
    confirm_as_user(db, EMAIL)
    monkeypatch.delenv("MAIL_BACKEND")
    assert sign_up(client, email=EMAIL).status_code == 503


def test_two_sign_ups_at_the_same_moment_end_quietly(client, db, monkeypatch):
    def collide(*args):
        raise IntegrityError("insert", {}, Exception("UNIQUE constraint failed"))
    monkeypatch.setattr(main, "issue_code", collide)
    response = sign_up(client)
    assert response.status_code == 202 and response.json() == {"status": "confirmation_sent"}
    assert db.query(models.User).count() == 0 and mailer.outbox == []


# ---------- the limit ----------
def test_the_sixth_request_in_an_hour_is_refused_before_anything_happens(client, db):
    for number in range(5):
        assert sign_up(client, email=f"person{number}@lab.br").status_code == 202
    response = sign_up(client, email="person6@lab.br")
    assert response.status_code == 429 and response.json()["detail"]["code"] == "too_many_attempts"
    assert 3500 < int(response.headers["Retry-After"]) <= 3600 and response.json()["detail"]["params"]["minutes"] == 60
    assert db.query(models.User).count() == 5 and len(mailer.outbox) == 5


def test_refused_requests_count_too(client):
    for _ in range(5):
        assert sign_up(client, email="nobody").status_code == 400
    assert sign_up(client).status_code == 429


def test_sign_ups_do_not_use_up_the_login_attempts(client, user):
    for _ in range(5):
        sign_up(client, email="nobody")
    assert client.post("/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 200


def test_failed_logins_do_not_use_up_the_sign_up_attempts(client):
    for _ in range(5):
        client.post("/login", json={"email": "x@lab.br", "password": "wrong-password"})
    assert sign_up(client).status_code == 202


# ---------- the helpers ----------
def test_a_code_is_long_random_and_hashes_the_same_way_every_time():
    codes = {email_confirmation.new_code() for _ in range(50)}
    assert len(codes) == 50 and all(len(c) >= 40 for c in codes)
    code = codes.pop()
    assert email_confirmation.hash_code(code) == email_confirmation.hash_code(code)
    assert re.fullmatch(r"[0-9a-f]{64}", email_confirmation.hash_code(code))
    assert email_confirmation.hash_code("a") != email_confirmation.hash_code("b")


def test_the_site_address_comes_from_the_environment_without_a_trailing_slash(monkeypatch):
    monkeypatch.setenv("SITE_URL", " https://site.example/// ")
    assert email_confirmation.site_url() == "https://site.example"


def test_the_site_address_defaults_only_in_development(monkeypatch):
    monkeypatch.delenv("SITE_URL")
    with pytest.raises(mailer.MailError, match="SITE_URL"):
        email_confirmation.site_url()
    monkeypatch.setenv("ENTOMOBASE_ENV", "dev")
    assert email_confirmation.site_url() == email_confirmation.DEV_SITE_URL
    monkeypatch.setenv("ENTOMOBASE_ENV", "prod")
    with pytest.raises(mailer.MailError):
        email_confirmation.site_url()
