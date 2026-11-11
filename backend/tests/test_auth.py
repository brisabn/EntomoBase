from datetime import timedelta

from fastapi.testclient import TestClient

from conftest import EMAIL, PASSWORD, make_token
from helpers import error_code, project_body


def login(client, email=EMAIL, password=PASSWORD):
    return client.post("/login", json={"email": email, "password": password})


def test_login_returns_a_token_that_works(client, user):
    response = login(client)
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == EMAIL
    created = client.post("/projects", json=project_body(), headers={"Authorization": f"Bearer {body['access_token']}"})
    assert created.status_code == 201


def test_wrong_password_is_refused(client, user):
    response = login(client, password="wrong-password")
    assert response.status_code == 401
    assert error_code(response) == "invalid_credentials"


def test_unknown_email_gets_the_same_answer_as_a_wrong_password(client, user):
    unknown = login(client, email="nobody@lab.br")
    wrong = login(client, password="wrong-password")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


def test_email_is_case_insensitive(client, user):
    assert login(client, email="ADMIN@Lab.BR").status_code == 200


def test_no_default_user_exists(client):
    assert login(client, email="admin@lab.br", password="123").status_code == 401


def test_short_password_is_a_validation_error(client, user):
    response = login(client, password="x")
    assert response.status_code == 422
    assert error_code(response) == "invalid_request"


# ---------- tokens ----------
def test_protected_route_without_token(client):
    response = client.post("/projects", json=project_body())
    assert response.status_code == 401
    assert error_code(response) == "missing_token"


def test_protected_route_with_a_garbage_token(client):
    response = client.post("/projects", json=project_body(), headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == 401
    assert error_code(response) == "session_expired"


def test_expired_token_is_refused(client, user):
    token = make_token(expires_in=timedelta(seconds=-5))
    response = client.post("/projects", json=project_body(), headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert error_code(response) == "session_expired"


def test_token_signed_with_another_key_is_refused(client, user):
    token = make_token(key="another-secret-key-also-with-32-bytes-ok")
    response = client.post("/projects", json=project_body(), headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_authorization_header_must_use_the_bearer_scheme(client, user):
    token = make_token()
    response = client.post("/projects", json=project_body(), headers={"Authorization": token})
    assert response.status_code == 401
    assert error_code(response) == "missing_token"


def test_every_write_route_requires_login(client):
    routes = [
        ("post", "/projects"), ("put", "/projects/1"), ("delete", "/projects/1"),
        ("post", "/specimens"), ("put", "/specimens/1"), ("delete", "/specimens/1"),
        ("post", "/specimens/import"), ("post", "/taxonomy/validate"),
    ]
    for method, path in routes:
        response = getattr(client, method)(path, **({} if method == "delete" else {"json": {}}))
        assert response.status_code == 401, f"{method.upper()} {path} did not require login"


# ---------- limit on wrong passwords ----------
def test_five_wrong_passwords_block_the_account_even_for_the_right_password(client, user):
    for _ in range(5):
        assert login(client, password="wrong-password").status_code == 401
    blocked = login(client)
    assert blocked.status_code == 429
    assert error_code(blocked) == "too_many_attempts"
    assert blocked.json()["detail"]["params"]["minutes"] == 15
    assert int(blocked.headers["Retry-After"]) == 15 * 60 or int(blocked.headers["Retry-After"]) > 800


def test_another_address_is_not_blocked(client, user, app):
    for _ in range(5):
        login(client, password="wrong-password")
    assert login(client).status_code == 429
    other = TestClient(app, client=("10.0.0.2", 50000))
    assert login(other).status_code == 200


def test_a_successful_login_resets_the_counter(client, user):
    for _ in range(4):
        login(client, password="wrong-password")
    assert login(client).status_code == 200
    for _ in range(4):
        assert login(client, password="wrong-password").status_code == 401


def test_twenty_wrong_passwords_block_the_address_for_every_account(client, user):
    for i in range(20):
        assert login(client, email=f"user{i}@lab.br", password="wrong-password").status_code == 401
    assert login(client).status_code == 429


def test_blocked_attempts_do_not_extend_the_block(client, user):
    from main import account_limiter
    for _ in range(5):
        login(client, password="wrong-password")
    for _ in range(10):
        assert login(client).status_code == 429
    assert len(account_limiter._failures[("testclient", EMAIL)]) == 5


# ---------- stored hash upgrade ----------
def test_a_weaker_stored_hash_is_upgraded_at_login(client, db):
    import models
    from argon2 import PasswordHasher
    from security import needs_rehash, verify_password
    weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash(PASSWORD)
    db.add(models.User(email=EMAIL, password_hash=weak))
    db.commit()
    assert needs_rehash(weak)
    assert login(client).status_code == 200
    db.expire_all()
    upgraded = db.query(models.User).one().password_hash
    assert upgraded != weak and not needs_rehash(upgraded) and verify_password(PASSWORD, upgraded)
