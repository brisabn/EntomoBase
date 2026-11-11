import models


def add_lab(db, slug, name, listed=True, **extra):
    lab = models.Laboratory(slug=slug, name=name, institution=extra.get("institution", "INST"), collection_code="COL", license="http://license.test", listed=listed)
    db.add(lab)
    db.commit()
    return lab


def test_the_list_is_empty_when_there_are_no_laboratories(client, db):
    assert client.get("/labs").json() == []
    assert db.query(models.Laboratory).count() == 0


def test_only_listed_laboratories_are_in_the_list(client, db):
    add_lab(db, "visible", "Visible lab")
    add_lab(db, "hidden", "Hidden lab", listed=False)
    assert [lab["slug"] for lab in client.get("/labs").json()] == ["visible"]


def test_a_laboratory_that_is_not_listed_still_works_at_its_address(client, db):
    add_lab(db, "hidden", "Hidden lab", listed=False)
    assert client.get("/labs/hidden/projects").status_code == 200


def test_the_list_is_ordered_by_name(client, db):
    add_lab(db, "c", "Charlie")
    add_lab(db, "a", "Alpha")
    add_lab(db, "b", "Bravo")
    assert [lab["name"] for lab in client.get("/labs").json()] == ["Alpha", "Bravo", "Charlie"]


def test_the_list_only_has_public_fields(client, db):
    add_lab(db, "visible", "Visible lab", institution="UFMG")
    lab = client.get("/labs").json()[0]
    assert lab == {"slug": "visible", "name": "Visible lab", "institution": "UFMG", "collection_code": "COL"}


def test_the_list_needs_no_login_and_ignores_a_bad_token(client, db):
    add_lab(db, "visible", "Visible lab")
    assert len(client.get("/labs").json()) == 1
    assert len(client.get("/labs", headers={"Authorization": "Bearer garbage"}).json()) == 1
