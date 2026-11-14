from datetime import timedelta

import pytest

import laboratory_requests
import mailer
import main
import models
from conftest import OUTSIDER_EMAIL, SUPERADMIN_EMAIL, add_user, make_token
from email_confirmation import utc_now
from mailer import MailError

SITE = "https://entomobase.example"
TRUSTED = "ana@icb.ufmg.br"
BODY = {"slug": "abelhas", "name": "Laboratório de Abelhas", "institution": "UFV", "collection_code": "ABE",
        "message": "Coleção de abelhas nativas."}


@pytest.fixture(autouse=True)
def mail_in_memory(monkeypatch):
    monkeypatch.setenv("MAIL_BACKEND", "memory")
    monkeypatch.setenv("SITE_URL", SITE)
    monkeypatch.setenv("TRUSTED_EMAIL_DOMAINS", "ufmg.br")
    monkeypatch.delenv("ENTOMOBASE_ENV", raising=False)
    mailer.outbox.clear()


def headers_of(email):
    return {"Authorization": f"Bearer {make_token(email=email)}"}


@pytest.fixture
def trusted(password_hash):
    add_user(TRUSTED, password_hash)
    return headers_of(TRUSTED)


def ask(client, headers, **overrides):
    return client.post("/laboratory-requests", json={**BODY, **overrides}, headers=headers)


def asked(client, headers, **overrides):
    response = ask(client, headers, **overrides)
    assert response.status_code == 201, response.text
    return response.json()


def lab(db, slug="abelhas"):
    db.expire_all()
    return db.query(models.Laboratory).filter_by(slug=slug).first()


def role_of(db, email, slug="abelhas"):
    db.expire_all()
    m = db.query(models.Membership).join(models.User).join(models.Laboratory).filter(
        models.User.email == email, models.Laboratory.slug == slug).first()
    return m.role if m else None


def mails_to(email):
    return [m for m in mailer.outbox if m["To"] == email]


def platform_list(client, superadmin):
    response = client.get("/platform/laboratory-requests", headers=superadmin)
    assert response.status_code == 200, response.text
    return response.json()


def approve(client, superadmin, request_id, **body):
    return client.post(f"/platform/laboratory-requests/{request_id}/approve", json=body, headers=superadmin)


def reject(client, superadmin, request_id, reason=None):
    return client.post(f"/platform/laboratory-requests/{request_id}/reject", json={"reason": reason}, headers=superadmin)


# ---------- asking ----------
def test_a_request_from_another_domain_waits_for_the_platform_administrator(client, outsider, db):
    request = asked(client, outsider)
    assert {k: request[k] for k in BODY} == BODY
    assert (request["status"], request["laboratory_slug"], request["decided_at"], request["decision_reason"]) == ("pending", None, None, None)
    assert set(request) == set(BODY) | {"id", "status", "created_at", "decided_at", "decision_reason", "laboratory_slug"}
    assert lab(db) is None


def test_the_platform_administrators_who_read_e_mail_are_told(client, outsider, superadmin, password_hash):
    add_user("unconfirmed.super@lab.br", password_hash, confirmed=False)
    add_user("other.super@lab.br", password_hash)
    db_users = {"unconfirmed.super@lab.br", "other.super@lab.br"}
    from conftest import SessionLocal
    session = SessionLocal()
    session.query(models.User).filter(models.User.email.in_(db_users)).update({"is_superadmin": True}, synchronize_session=False)
    session.commit()
    session.close()
    asked(client, outsider)
    assert sorted(m["To"] for m in mailer.outbox) == ["other.super@lab.br", SUPERADMIN_EMAIL]
    message = mails_to(SUPERADMIN_EMAIL)[0]
    assert message["Subject"] == "EntomoBase: pedido de laboratório / laboratory request"
    text = message.get_content()
    for part in ("aguarda sua decisão", "Laboratório de Abelhas", "UFV", "ABE", "lab/abelhas", OUTSIDER_EMAIL,
                 "Coleção de abelhas nativas.", f"{SITE}/#/platform"):
        assert part in text, part


def test_without_a_platform_administrator_the_request_still_waits(client, outsider):
    assert asked(client, outsider)["status"] == "pending"
    assert mailer.outbox == []


def test_an_address_of_a_trusted_domain_opens_the_laboratory_at_once(client, trusted, superadmin, db):
    request = asked(client, trusted)
    assert (request["status"], request["laboratory_slug"]) == ("approved", "abelhas")
    assert request["decided_at"] is not None
    created = lab(db)
    assert (created.name, created.institution, created.collection_code, created.listed) == ("Laboratório de Abelhas", "UFV", "ABE", False)
    assert created.license == main.DEFAULT_LABORATORY["license"]
    assert role_of(db, TRUSTED) == "admin"
    assert db.query(models.Membership).filter_by(laboratory_id=created.id).count() == 1
    row = db.query(models.LaboratoryRequest).one()
    assert (row.decided_by_id, row.laboratory_id) == (None, created.id)
    # the platform administrator is told it exists
    assert "foi criado na hora" in mails_to(SUPERADMIN_EMAIL)[0].get_content()
    # and the person already manages it
    assert client.get("/labs/abelhas/members", headers=trusted).status_code == 200


def test_the_laboratory_opened_by_the_domain_stays_out_of_the_public_list(client, trusted):
    asked(client, trusted)
    assert "abelhas" not in [l["slug"] for l in client.get("/labs").json()]
    assert client.get("/labs/abelhas/laboratory").status_code == 200


@pytest.mark.parametrize("email", ["ana@ufmg.br", "ana@icb.ufmg.br"])
def test_the_domain_and_its_subdomains_are_trusted(client, password_hash, email):
    add_user(email, password_hash)
    assert asked(client, headers_of(email))["status"] == "approved"


@pytest.mark.parametrize("email", ["ana@ufmg.br.example.com", "ana@notufmg.br", "ana@gmail.com"])
def test_lookalike_domains_are_not_trusted(client, password_hash, email):
    add_user(email, password_hash)
    assert asked(client, headers_of(email))["status"] == "pending"


def test_one_request_waits_at_a_time_per_person(client, outsider, superadmin):
    first = asked(client, outsider)
    response = ask(client, outsider, slug="outro", name="Outro")
    assert (response.status_code, response.json()["detail"]["code"]) == (400, "request_pending")
    # once the first is decided, the person may ask again
    assert reject(client, superadmin, first["id"]).status_code == 200
    assert ask(client, outsider, slug="outro", name="Outro").status_code == 201


def test_the_address_of_an_existing_laboratory_cannot_be_asked_for(client, admin, outsider):
    # the admin fixture creates the first laboratory, ufmg
    response = ask(client, outsider, slug="ufmg")
    assert (response.status_code, response.json()["detail"]["code"]) == (400, "duplicate_slug")


def test_an_address_held_by_a_waiting_request_cannot_be_asked_for(client, outsider, researcher, superadmin):
    first = asked(client, outsider)
    response = ask(client, researcher)
    assert (response.status_code, response.json()["detail"]["code"]) == (400, "duplicate_slug")
    # a refused request lets go of the address
    reject(client, superadmin, first["id"])
    assert ask(client, researcher).status_code == 201


def test_a_few_requests_a_day_per_person(client, trusted, monkeypatch):
    for n in range(laboratory_requests.REQUESTS_PER_DAY):
        assert ask(client, trusted, slug=f"lab-{n}").status_code == 201
    response = ask(client, trusted, slug="one-more")
    assert (response.status_code, response.json()["detail"]["code"]) == (429, "too_many_attempts")
    assert "Retry-After" in response.headers


def test_refused_attempts_do_not_count_toward_the_daily_limit(client, admin, trusted):
    for _ in range(5):
        assert ask(client, trusted, slug="ufmg").status_code == 400
    assert ask(client, trusted).status_code == 201


def test_the_limit_is_per_person(client, trusted, outsider):
    for n in range(laboratory_requests.REQUESTS_PER_DAY):
        ask(client, trusted, slug=f"lab-{n}")
    assert ask(client, outsider).status_code == 201


def test_the_texts_are_trimmed_and_an_empty_message_is_none(client, outsider):
    request = asked(client, outsider, name="  Abelhas  ", institution=" UFV ", collection_code=" ABE ", message="   ")
    assert (request["name"], request["institution"], request["collection_code"], request["message"]) == ("Abelhas", "UFV", "ABE", None)


@pytest.mark.parametrize("field,value", [
    ("slug", "Abelhas"), ("slug", "a"), ("slug", "abelhas-"), ("slug", "x" * 41), ("name", ""), ("institution", ""),
    ("collection_code", ""), ("message", "x" * 2001), ("name", "x" * 201),
])
def test_invalid_fields_are_refused(client, outsider, field, value):
    assert ask(client, outsider, **{field: value}).status_code == 422


def test_a_visitor_cannot_ask(client):
    assert ask(client, {}).status_code == 401


def test_when_the_e_mail_cannot_be_sent_nothing_is_kept(client, trusted, db, monkeypatch):
    def fail(*args):
        raise MailError("down")
    monkeypatch.setattr(main, "send_new_request", fail)
    response = ask(client, trusted)
    assert (response.status_code, response.json()["detail"]["code"]) == (503, "mail_unavailable")
    assert db.query(models.LaboratoryRequest).count() == 0
    assert lab(db) is None
    # and it does not count toward the limit
    monkeypatch.setattr(main, "send_new_request", laboratory_requests.send_new_request)
    for n in range(laboratory_requests.REQUESTS_PER_DAY):
        assert ask(client, trusted, slug=f"lab-{n}").status_code == 201


def test_an_address_taken_at_the_same_moment_is_refused_and_nothing_is_kept(client, trusted, db, monkeypatch):
    db.add(models.Laboratory(slug="abelhas", name="Other", institution="X", collection_code="X", license="x"))
    db.commit()
    monkeypatch.setattr(main, "address_taken", lambda db, slug: False)
    response = ask(client, trusted)
    assert (response.status_code, response.json()["detail"]["code"]) == (400, "duplicate_slug")
    db.expire_all()
    assert db.query(models.LaboratoryRequest).count() == 0
    assert lab(db).name == "Other"


# ---------- the person's own requests ----------
def test_each_person_sees_only_their_own_requests_newest_first(client, outsider, researcher, superadmin, db):
    first = asked(client, outsider, slug="primeiro")
    reject(client, superadmin, first["id"], "Faltam dados")
    second = asked(client, outsider, slug="segundo")
    asked(client, researcher, slug="de-outra-pessoa")
    mine = client.get("/me/laboratory-requests", headers=outsider).json()
    assert [(r["id"], r["status"]) for r in mine] == [(second["id"], "pending"), (first["id"], "rejected")]
    assert mine[1]["decision_reason"] == "Faltam dados"
    assert "requester_email" not in mine[0]
    assert [r["slug"] for r in client.get("/me/laboratory-requests", headers=researcher).json()] == ["de-outra-pessoa"]


def test_the_newest_comes_first_even_at_the_same_moment(client, outsider, superadmin, db):
    first = asked(client, outsider, slug="primeiro")
    reject(client, superadmin, first["id"])
    second = asked(client, outsider, slug="segundo")
    db.query(models.LaboratoryRequest).update({"created_at": utc_now() - timedelta(days=1)})
    db.commit()
    assert [r["id"] for r in client.get("/me/laboratory-requests", headers=outsider).json()] == [second["id"], first["id"]]


def test_a_waiting_request_can_be_withdrawn_by_whoever_made_it(client, outsider, db):
    request = asked(client, outsider)
    assert client.delete(f"/me/laboratory-requests/{request['id']}", headers=outsider).status_code == 204
    assert db.query(models.LaboratoryRequest).count() == 0
    # and the address is free again
    assert ask(client, outsider).status_code == 201


def test_someone_elses_request_is_the_same_as_none(client, outsider, researcher, superadmin):
    request = asked(client, outsider)
    for headers in (researcher, superadmin):
        response = client.delete(f"/me/laboratory-requests/{request['id']}", headers=headers)
        assert (response.status_code, response.json()["detail"]["code"]) == (404, "request_not_found")
    assert client.delete("/me/laboratory-requests/99999", headers=outsider).json()["detail"]["code"] == "request_not_found"
    assert client.get("/me/laboratory-requests", headers=outsider).json()[0]["status"] == "pending"


def test_a_decided_request_cannot_be_withdrawn(client, trusted):
    request = asked(client, trusted)
    response = client.delete(f"/me/laboratory-requests/{request['id']}", headers=trusted)
    assert (response.status_code, response.json()["detail"]["code"]) == (400, "request_already_decided")


# ---------- the platform administrator ----------
def test_the_platform_administrator_sees_the_waiting_ones_first_oldest_first(client, outsider, researcher, trusted, superadmin, db):
    old = asked(client, outsider, slug="antigo")
    new = asked(client, researcher, slug="novo")
    auto = asked(client, trusted, slug="automatico")
    db.query(models.LaboratoryRequest).filter_by(id=old["id"]).update({"created_at": utc_now() - timedelta(days=2)})
    db.commit()
    rows = platform_list(client, superadmin)
    assert [r["slug"] for r in rows] == ["antigo", "novo", "automatico"]
    assert (rows[0]["requester_email"], rows[2]["decided_by_email"], rows[2]["laboratory_slug"]) == (OUTSIDER_EMAIL, None, "automatico")
    assert rows[0]["message"] == BODY["message"]
    assert auto["id"] == rows[2]["id"] and new["id"] == rows[1]["id"]


def test_the_decided_ones_come_newest_first_and_only_the_latest(client, trusted, superadmin, db, monkeypatch):
    monkeypatch.setattr(main, "LAB_REQUESTS_DECIDED_LIMIT", 2)
    for n in range(3):
        asked(client, trusted, slug=f"lab-{n}")
    rows = platform_list(client, superadmin)
    assert [r["slug"] for r in rows] == ["lab-2", "lab-1"]


def test_the_decided_ones_at_the_same_moment_come_newest_first(client, trusted, superadmin, db):
    for n in range(2):
        asked(client, trusted, slug=f"lab-{n}")
    db.query(models.LaboratoryRequest).update({"decided_at": utc_now() - timedelta(days=1)})
    db.commit()
    assert [r["slug"] for r in platform_list(client, superadmin)] == ["lab-1", "lab-0"]


def test_approving_opens_the_laboratory_with_whoever_asked_as_admin(client, outsider, superadmin, db):
    request = asked(client, outsider)
    mailer.outbox.clear()
    response = approve(client, superadmin, request["id"])
    assert response.status_code == 200, response.text
    decided = response.json()
    assert (decided["status"], decided["laboratory_slug"], decided["decided_by_email"]) == ("approved", "abelhas", SUPERADMIN_EMAIL)
    assert lab(db).listed is False
    assert role_of(db, OUTSIDER_EMAIL) == "admin"
    assert role_of(db, SUPERADMIN_EMAIL) is None
    [message] = mails_to(OUTSIDER_EMAIL)
    assert message["Subject"] == "EntomoBase: seu laboratório foi criado / your laboratory was created"
    text = message.get_content()
    assert f"{SITE}/#/lab/abelhas" in text and "fora da lista pública" in text and "Laboratório de Abelhas" in text
    # the person sees it on their side too
    assert client.get("/me/laboratory-requests", headers=outsider).json()[0]["laboratory_slug"] == "abelhas"


def test_the_platform_administrator_may_list_it_when_approving(client, outsider, superadmin, db):
    request = asked(client, outsider)
    assert approve(client, superadmin, request["id"], listed=True).status_code == 200
    assert lab(db).listed is True
    assert "abelhas" in [l["slug"] for l in client.get("/labs").json()]
    assert "já aparece na lista pública" in mails_to(OUTSIDER_EMAIL)[-1].get_content()


def test_refusing_keeps_the_reason_and_tells_the_person(client, outsider, superadmin, db):
    request = asked(client, outsider)
    response = reject(client, superadmin, request["id"], "  Use o laboratório que já existe.  ")
    assert response.status_code == 200, response.text
    decided = response.json()
    assert (decided["status"], decided["decision_reason"], decided["decided_by_email"], decided["laboratory_slug"]) == (
        "rejected", "Use o laboratório que já existe.", SUPERADMIN_EMAIL, None)
    assert decided["decided_at"] is not None
    assert lab(db) is None
    [message] = mails_to(OUTSIDER_EMAIL)
    assert message["Subject"] == "EntomoBase: pedido de laboratório recusado / laboratory request refused"
    assert "Motivo:\nUse o laboratório que já existe." in message.get_content()


def test_refusing_without_a_reason(client, outsider, superadmin):
    request = asked(client, outsider)
    assert reject(client, superadmin, request["id"], "   ").json()["decision_reason"] is None
    assert "Motivo" not in mails_to(OUTSIDER_EMAIL)[0].get_content()


def test_refusing_with_an_empty_body(client, outsider, superadmin):
    request = asked(client, outsider)
    response = client.post(f"/platform/laboratory-requests/{request['id']}/reject", json={}, headers=superadmin)
    assert (response.status_code, response.json()["decision_reason"]) == (200, None)


def test_a_reason_too_long_is_refused(client, outsider, superadmin):
    request = asked(client, outsider)
    assert reject(client, superadmin, request["id"], "x" * 1001).status_code == 422


def test_a_decided_request_cannot_be_decided_again(client, outsider, superadmin):
    request = asked(client, outsider)
    approve(client, superadmin, request["id"])
    for response in (approve(client, superadmin, request["id"]), reject(client, superadmin, request["id"])):
        assert (response.status_code, response.json()["detail"]["code"]) == (400, "request_already_decided")


def test_an_unknown_request_is_a_404(client, superadmin):
    for response in (approve(client, superadmin, 99999), reject(client, superadmin, 99999)):
        assert (response.status_code, response.json()["detail"]["code"]) == (404, "request_not_found")


def test_an_address_taken_in_the_meantime_cannot_be_approved(client, outsider, superadmin, db):
    request = asked(client, outsider)
    assert client.post("/labs", json={"slug": "abelhas", "name": "Outro", "institution": "X", "collection_code": "X",
                                      "admin_email": SUPERADMIN_EMAIL}, headers=superadmin).status_code == 201
    response = approve(client, superadmin, request["id"])
    assert (response.status_code, response.json()["detail"]["code"]) == (400, "duplicate_slug")
    assert platform_list(client, superadmin)[0]["status"] == "pending"
    assert role_of(db, OUTSIDER_EMAIL) is None


def test_an_address_taken_at_the_moment_of_approving_is_refused(client, outsider, superadmin, db, monkeypatch):
    request = asked(client, outsider)
    db.add(models.Laboratory(slug="abelhas", name="Other", institution="X", collection_code="X", license="x"))
    db.commit()
    monkeypatch.setattr(main, "address_taken", lambda db, slug: False)
    response = approve(client, superadmin, request["id"])
    assert (response.status_code, response.json()["detail"]["code"]) == (400, "duplicate_slug")
    assert platform_list(client, superadmin)[0]["status"] == "pending"


@pytest.mark.parametrize("decide", [approve, reject])
def test_when_the_decision_cannot_be_sent_nothing_changes(client, outsider, superadmin, db, monkeypatch, decide):
    request = asked(client, outsider)

    def fail(*args):
        raise MailError("down")
    monkeypatch.setattr(main, "send_decision", fail)
    response = decide(client, superadmin, request["id"])
    assert (response.status_code, response.json()["detail"]["code"]) == (503, "mail_unavailable")
    assert platform_list(client, superadmin)[0]["status"] == "pending"
    assert lab(db) is None


# ---------- the public list ----------
def test_the_platform_administrator_puts_a_laboratory_in_the_public_list_and_takes_it_out(client, trusted, superadmin):
    asked(client, trusted)
    response = client.put("/platform/laboratories/abelhas", json={"listed": True}, headers=superadmin)
    assert response.status_code == 200, response.text
    assert {k: response.json()[k] for k in ("slug", "listed", "members", "admins")} == {"slug": "abelhas", "listed": True, "members": 1, "admins": [TRUSTED]}
    assert "abelhas" in [l["slug"] for l in client.get("/labs").json()]
    client.put("/platform/laboratories/abelhas", json={"listed": False}, headers=superadmin)
    assert "abelhas" not in [l["slug"] for l in client.get("/labs").json()]


def test_the_admin_of_the_laboratory_cannot_list_it(client, trusted):
    asked(client, trusted)
    assert client.put("/platform/laboratories/abelhas", json={"listed": True}, headers=trusted).status_code == 403


def test_listing_an_unknown_laboratory_is_a_404(client, admin, superadmin):
    response = client.put("/platform/laboratories/nowhere", json={"listed": True}, headers=superadmin)
    assert (response.status_code, response.json()["detail"]["code"]) == (404, "lab_not_found")
    assert client.put("/platform/laboratories/ufmg", json={}, headers=superadmin).status_code == 422
