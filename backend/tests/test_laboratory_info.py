import models


def add_lab(db, slug, name, listed):
    db.add(models.Laboratory(slug=slug, name=name, institution="INST", collection_code="CODE", license="x", listed=listed))
    db.commit()


def test_a_laboratory_tells_its_public_data(client, user, db):
    add_lab(db, "lab-b", "Lab B", True)
    response = client.get("/labs/lab-b/laboratory")
    assert response.status_code == 200
    assert response.json() == {"slug": "lab-b", "name": "Lab B", "institution": "INST", "collection_code": "CODE"}


def test_an_unlisted_laboratory_answers_too(client, user, db):
    add_lab(db, "hidden", "Hidden lab", False)
    assert client.get("/labs/hidden/laboratory").json()["name"] == "Hidden lab"


def test_the_old_address_is_the_first_laboratory(client, user, db):
    add_lab(db, "aaa", "A first by name", True)
    assert client.get("/laboratory").json()["slug"] == "ufmg"


def test_an_unknown_laboratory_is_a_404(client, user):
    response = client.get("/labs/nowhere/laboratory")
    assert response.status_code == 404 and response.json()["detail"]["code"] == "lab_not_found"


def test_nothing_internal_is_sent(client, user, db):
    add_lab(db, "lab-b", "Lab B", False)
    body = client.get("/labs/lab-b/laboratory").json()
    assert set(body) == {"slug", "name", "institution", "collection_code"}


def test_members_and_strangers_get_the_same_answer(client, admin, outsider):
    assert client.get("/laboratory", headers=admin).json() == client.get("/laboratory", headers=outsider).json() == client.get("/laboratory").json()
