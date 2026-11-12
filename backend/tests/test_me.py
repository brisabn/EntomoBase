import models
from conftest import EMAIL, RESEARCHER_EMAIL, make_token


def lab(db, slug, name):
    laboratory = models.Laboratory(slug=slug, name=name, institution="I", collection_code="C", license="x")
    db.add(laboratory)
    db.commit()
    return laboratory


def join(db, email, laboratory, role):
    user = db.query(models.User).filter_by(email=email).one()
    db.add(models.Membership(user_id=user.id, laboratory_id=laboratory.id, role=role))
    db.commit()


def test_an_admin_sees_their_account_and_laboratory(client, admin):
    response = client.get("/me", headers=admin)
    assert response.status_code == 200
    assert response.json() == {"email": EMAIL, "name": None, "is_superadmin": False,
                               "laboratories": [{"slug": "ufmg", "name": "EntomoBase UFMG", "role": "admin"}]}


def test_the_laboratories_are_ordered_by_name_with_the_role_in_each(client, admin, db):
    join(db, EMAIL, lab(db, "zeta", "Zeta lab"), "researcher")
    join(db, EMAIL, lab(db, "alpha", "Alpha lab"), "admin")
    lab(db, "other", "Another lab")
    assert [(l["slug"], l["role"]) for l in client.get("/me", headers=admin).json()["laboratories"]] == [
        ("alpha", "admin"), ("ufmg", "admin"), ("zeta", "researcher")]


def test_a_researcher_sees_their_role(client, admin, researcher):
    assert client.get("/me", headers=researcher).json()["laboratories"] == [{"slug": "ufmg", "name": "EntomoBase UFMG", "role": "researcher"}]


def test_someone_without_a_laboratory_gets_an_empty_list(client, admin, outsider):
    assert client.get("/me", headers=outsider).json()["laboratories"] == []


def test_the_name_and_the_platform_flag_are_shown(client, superadmin, db):
    db.query(models.User).filter_by(email="super@lab.br").update({"name": "Super"})
    db.commit()
    body = client.get("/me", headers=superadmin).json()
    assert (body["name"], body["is_superadmin"], body["laboratories"]) == ("Super", True, [])


def test_a_role_change_shows_at_once(client, admin, researcher, db):
    db.query(models.Membership).join(models.User).filter(models.User.email == RESEARCHER_EMAIL).one().role = "admin"
    db.commit()
    assert client.get("/me", headers=researcher).json()["laboratories"][0]["role"] == "admin"


def test_nothing_private_is_sent(client, admin):
    body = client.get("/me", headers=admin).json()
    assert set(body) == {"email", "name", "is_superadmin", "laboratories"} and "password" not in str(body)


def test_without_a_session_it_is_a_401(client, admin):
    assert client.get("/me").status_code == 401
    assert client.get("/me", headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_an_expired_session_is_a_401(client, admin):
    from datetime import timedelta
    token = make_token(expires_in=timedelta(seconds=-1))
    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401 and response.json()["detail"]["code"] == "session_expired"


def test_there_is_no_me_inside_a_laboratory(client, admin):
    assert client.get("/labs/ufmg/me", headers=admin).status_code == 404
