import getpass
import sys

import pytest

import create_admin
import models
from conftest import EMAIL, PASSWORD
from security import verify_password


@pytest.fixture
def run(monkeypatch, capsys):
    # runs the script as if typed in a terminal: arguments, then the answers to the password prompts
    def execute(args, *passwords):
        answers = iter(passwords)
        monkeypatch.setattr(getpass, "getpass", lambda prompt="": next(answers))
        monkeypatch.setattr(sys, "argv", ["create_admin.py", *args])
        code = create_admin.main()
        return code, capsys.readouterr().out
    return execute


def test_creates_a_user_who_can_log_in(run, client, db):
    code, output = run([EMAIL], PASSWORD, PASSWORD)
    assert code == 0 and "created" in output
    assert db.query(models.User).count() == 1
    assert client.post("/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 200


def test_the_password_is_stored_as_a_hash(run, db):
    run([EMAIL], PASSWORD, PASSWORD)
    stored = db.query(models.User).one().password_hash
    assert stored != PASSWORD and verify_password(PASSWORD, stored)


def test_the_email_is_stored_in_lowercase(run, db):
    run(["Admin@Lab.BR"], PASSWORD, PASSWORD)
    assert db.query(models.User).one().email == "admin@lab.br"


def test_running_again_changes_the_password(run, client, db):
    run([EMAIL], PASSWORD, PASSWORD)
    code, output = run([EMAIL], "another-password", "another-password")
    assert code == 0 and "updated" in output
    assert db.query(models.User).count() == 1
    assert client.post("/login", json={"email": EMAIL, "password": "another-password"}).status_code == 200
    assert client.post("/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 401


def test_a_short_password_is_refused(run, db):
    code, output = run([EMAIL], "short", "short")
    assert code == 1 and "8" in output
    assert db.query(models.User).count() == 0


def test_passwords_that_do_not_match_are_refused(run, db):
    code, output = run([EMAIL], PASSWORD, "another-password")
    assert code == 1
    assert db.query(models.User).count() == 0


@pytest.mark.parametrize("args", [[], ["not-an-email"], [EMAIL, "extra"]])
def test_wrong_arguments_print_the_usage(run, args, db):
    code, output = run(args)
    assert code == 1 and "Usage" in output
    assert db.query(models.User).count() == 0


# ---------- laboratory membership ----------
def test_a_new_user_becomes_an_admin_of_the_first_laboratory(run, db):
    code, output = run([EMAIL], PASSWORD, PASSWORD)
    membership = db.query(models.Membership).one()
    assert membership.role == "admin" and membership.laboratory.slug == "ufmg" and membership.user.email == EMAIL
    assert "admin of the laboratory" in output


def test_the_new_admin_can_create_a_project_right_away(run, client):
    from helpers import project_body
    run([EMAIL], PASSWORD, PASSWORD)
    token = client.post("/login", json={"email": EMAIL, "password": PASSWORD}).json()["access_token"]
    response = client.post("/projects", json=project_body(), headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 201


def test_running_again_does_not_duplicate_the_membership(run, db):
    run([EMAIL], PASSWORD, PASSWORD)
    _, output = run([EMAIL], PASSWORD, PASSWORD)
    assert db.query(models.Membership).count() == 1
    assert "admin of the laboratory" not in output


def test_an_existing_user_without_a_membership_gets_one(run, db, password_hash):
    from conftest import add_user
    add_user(EMAIL, password_hash)
    assert db.query(models.Membership).count() == 0
    run([EMAIL], PASSWORD, PASSWORD)
    assert db.query(models.Membership).one().role == "admin"


def test_a_researcher_keeps_the_role_when_the_password_is_changed(run, db, password_hash):
    from conftest import add_user
    add_user(EMAIL, password_hash, role="researcher")
    run([EMAIL], PASSWORD, PASSWORD)
    assert db.query(models.Membership).one().role == "researcher"
