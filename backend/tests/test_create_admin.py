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


# ---------- --superadmin ----------
def test_a_user_is_not_a_platform_administrator_by_default(run, db):
    run([EMAIL], PASSWORD, PASSWORD)
    assert db.query(models.User).one().is_superadmin is False


def test_the_flag_makes_a_platform_administrator(run, db):
    code, output = run([EMAIL, "--superadmin"], PASSWORD, PASSWORD)
    assert code == 0 and "platform administrator" in output
    assert db.query(models.User).one().is_superadmin is True


def test_the_flag_can_come_before_the_email(run, db):
    run(["--superadmin", EMAIL], PASSWORD, PASSWORD)
    assert db.query(models.User).one().is_superadmin is True


def test_the_flag_still_makes_the_user_an_admin_of_the_first_laboratory(run, db):
    run([EMAIL, "--superadmin"], PASSWORD, PASSWORD)
    assert db.query(models.Membership).one().role == "admin"


def test_the_flag_can_be_added_to_an_existing_user(run, db, password_hash):
    from conftest import add_user
    add_user(EMAIL, password_hash, role="researcher")
    run([EMAIL, "--superadmin"], PASSWORD, PASSWORD)
    user = db.query(models.User).one()
    assert user.is_superadmin is True and db.query(models.Membership).one().role == "researcher"


def test_running_again_without_the_flag_keeps_the_permission(run, db):
    run([EMAIL, "--superadmin"], PASSWORD, PASSWORD)
    _, output = run([EMAIL], PASSWORD, PASSWORD)
    assert db.query(models.User).one().is_superadmin is True
    assert "platform administrator" not in output


def test_running_again_with_the_flag_does_not_repeat_the_message(run):
    run([EMAIL, "--superadmin"], PASSWORD, PASSWORD)
    _, output = run([EMAIL, "--superadmin"], PASSWORD, PASSWORD)
    assert "platform administrator" not in output


def test_the_new_platform_administrator_can_create_a_laboratory(run, client):
    run([EMAIL, "--superadmin"], PASSWORD, PASSWORD)
    token = client.post("/login", json={"email": EMAIL, "password": PASSWORD}).json()["access_token"]
    body = {"slug": "second", "name": "Second", "institution": "S", "collection_code": "S", "admin_email": EMAIL}
    assert client.post("/labs", json=body, headers={"Authorization": f"Bearer {token}"}).status_code == 201


@pytest.mark.parametrize("args", [["--superadmin"], ["--superadmin", "--superadmin"], [EMAIL, "--superadmin", "extra"], ["not-an-email", "--superadmin"]])
def test_the_usage_is_shown_for_a_wrong_use_of_the_flag(run, args, db):
    code, output = run(args)
    assert code == 1 and "Usage" in output and "--superadmin" in output
    assert db.query(models.User).count() == 0
