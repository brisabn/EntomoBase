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


# ---------- creating a laboratory ----------
import pytest

from conftest import EMAIL
from helpers import project_body


def lab_body(**overrides):
    body = {"slug": "new-lab", "name": "New lab", "institution": "NEW", "collection_code": "NL", "admin_email": EMAIL}
    body.update(overrides)
    return body


def test_a_platform_administrator_creates_a_laboratory(client, superadmin, user):
    response = client.post("/labs", json=lab_body(listed=True), headers=superadmin)
    assert response.status_code == 201
    assert response.json() == {"slug": "new-lab", "name": "New lab", "institution": "NEW", "collection_code": "NL"}
    assert {lab["slug"] for lab in client.get("/labs").json()} == {"ufmg", "new-lab"}


def test_a_new_laboratory_is_not_listed_unless_asked(client, superadmin, user, db):
    client.post("/labs", json=lab_body(), headers=superadmin)
    assert [lab["slug"] for lab in client.get("/labs").json()] == ["ufmg"]
    assert db.query(models.Laboratory).filter_by(slug="new-lab").one().listed is False


def test_the_named_user_becomes_its_only_admin(client, superadmin, user, db):
    client.post("/labs", json=lab_body(), headers=superadmin)
    membership = db.query(models.Membership).join(models.Laboratory).filter(models.Laboratory.slug == "new-lab").one()
    assert membership.role == "admin"
    assert membership.user.email == EMAIL
    assert db.query(models.Membership).filter_by(laboratory_id=membership.laboratory_id).count() == 1


def test_that_admin_can_work_in_the_new_laboratory_but_not_in_other_ones(client, superadmin, admin, db):
    other = models.Laboratory(slug="old", name="Old", institution="O", collection_code="O", license="x", listed=True)
    db.add(other)
    db.commit()
    client.post("/labs", json=lab_body(), headers=superadmin)
    assert client.post("/labs/new-lab/projects", json=project_body(), headers=admin).status_code == 201
    assert client.post("/labs/old/projects", json=project_body(), headers=admin).status_code == 403


def test_the_admin_email_is_matched_ignoring_case_and_spaces(client, superadmin, user):
    response = client.post("/labs", json=lab_body(admin_email="  ADMIN@Lab.BR "), headers=superadmin)
    assert response.status_code == 201


def test_the_laboratory_gets_the_default_license_or_the_given_one(client, superadmin, user, db):
    client.post("/labs", json=lab_body(slug="default-license"), headers=superadmin)
    client.post("/labs", json=lab_body(slug="own-license", license="http://own.test"), headers=superadmin)
    licenses = {lab.slug: lab.license for lab in db.query(models.Laboratory).filter(models.Laboratory.slug != "ufmg").all()}
    assert licenses == {"default-license": "http://creativecommons.org/licenses/by/4.0/legalcode", "own-license": "http://own.test"}


def test_the_platform_administrator_does_not_get_access_to_the_laboratory(client, superadmin, user, db):
    client.post("/labs", json=lab_body(), headers=superadmin)
    assert db.query(models.Membership).join(models.User).filter(models.User.is_superadmin == True).count() == 0
    assert client.post("/labs/new-lab/projects", json=project_body(), headers=superadmin).status_code == 403


def test_a_visitor_cannot_create_a_laboratory(client, user):
    response = client.post("/labs", json=lab_body())
    assert response.status_code == 401 and response.json()["detail"]["code"] == "missing_token"


def test_a_lab_admin_is_not_a_platform_administrator(client, admin, db):
    response = client.post("/labs", json=lab_body(), headers=admin)
    assert response.status_code == 403 and response.json()["detail"]["code"] == "forbidden"
    assert db.query(models.Laboratory).filter_by(slug="new-lab").count() == 0


def test_the_platform_administrator_flag_comes_from_the_database(client, superadmin, user, db):
    db.query(models.User).update({"is_superadmin": False})
    db.commit()
    assert client.post("/labs", json=lab_body(), headers=superadmin).status_code == 403


def test_a_slug_that_exists_is_refused(client, superadmin, user, db):
    assert client.post("/labs", json=lab_body(), headers=superadmin).status_code == 201
    response = client.post("/labs", json=lab_body(name="Another"), headers=superadmin)
    assert response.status_code == 400 and response.json()["detail"]["code"] == "duplicate_slug"
    assert db.query(models.Laboratory).filter_by(slug="new-lab").count() == 1


# the check passes (another request had not committed yet) and the database refuses the second one
def test_a_race_on_the_slug_is_also_a_duplicate(client, superadmin, user, db, monkeypatch):
    import main
    db.add(models.Laboratory(slug="new-lab", name="First", institution="I", collection_code="C", license="x", listed=False))
    db.commit()
    original = main.Session.query

    def blind_to_laboratories(self, *entities, **kwargs):
        query = original(self, *entities, **kwargs)
        if entities and entities[0] is models.Laboratory:
            return query.filter(models.Laboratory.id < 0)
        return query
    monkeypatch.setattr(main.Session, "query", blind_to_laboratories)
    response = client.post("/labs", json=lab_body(), headers=superadmin)
    assert response.status_code == 400 and response.json()["detail"]["code"] == "duplicate_slug"


def test_an_unknown_admin_creates_nothing(client, superadmin, user, db):
    response = client.post("/labs", json=lab_body(admin_email="nobody@lab.br"), headers=superadmin)
    assert response.status_code == 404 and response.json()["detail"]["code"] == "user_not_found"
    # only the first laboratory (made by the user fixture) and its one membership exist
    assert [lab.slug for lab in db.query(models.Laboratory).all()] == ["ufmg"] and db.query(models.Membership).count() == 1


@pytest.mark.parametrize("slug", ["", "a", "UPPER", "Mixed", "with space", "-start", "end-", "a--b", "a/b", "a_b", "ü", "x" * 41, "a.b", ".."])
def test_a_slug_that_is_not_safe_for_an_address_is_refused(client, superadmin, user, db, slug):
    response = client.post("/labs", json=lab_body(slug=slug), headers=superadmin)
    assert response.status_code == 422
    assert any(p["field"] == "slug" for p in response.json()["detail"]["problems"])
    assert [lab.slug for lab in db.query(models.Laboratory).all()] == ["ufmg"]


@pytest.mark.parametrize("slug", ["ab", "lab1", "lab-ufmg", "museu-de-zoologia", "a1-b2-c3", "x" * 40])
def test_good_slugs_are_accepted(client, superadmin, user, slug):
    assert client.post("/labs", json=lab_body(slug=slug), headers=superadmin).status_code == 201


@pytest.mark.parametrize("missing", ["slug", "name", "institution", "collection_code", "admin_email"])
def test_every_required_field_is_checked(client, superadmin, user, missing):
    body = lab_body()
    del body[missing]
    response = client.post("/labs", json=body, headers=superadmin)
    assert response.status_code == 422
    assert (missing, "required") in {(p["field"], p["code"]) for p in response.json()["detail"]["problems"]}


def test_names_are_stored_without_surrounding_spaces(client, superadmin, user, db):
    client.post("/labs", json=lab_body(name="  Spaced  ", institution=" INST ", collection_code=" CC "), headers=superadmin)
    lab = db.query(models.Laboratory).filter_by(slug="new-lab").one()
    assert (lab.name, lab.institution, lab.collection_code) == ("Spaced", "INST", "CC")


def test_the_new_laboratory_is_reachable_at_its_address(client, superadmin, user):
    client.post("/labs", json=lab_body(), headers=superadmin)
    assert client.get("/labs/new-lab/projects").json() == []
