import re
import sys

import pytest

import models
import seed
from conftest import EMAIL
from helpers import create_specimen


@pytest.fixture
def run_seed(monkeypatch, capsys):
    def execute(*args):
        monkeypatch.setattr(sys, "argv", ["seed.py", *args])
        seed.main()
        return capsys.readouterr().out
    return execute


def test_seed_creates_the_demo_projects_and_specimens(run_seed, db):
    output = run_seed()
    assert db.query(models.Project).count() == len(seed.PROJECTS)
    specimens = db.query(models.Specimen).count()
    assert specimens == sum(p["n"] for p in seed.PROJECTS) and f"{specimens} demo specimens created" in output


def test_demo_data_is_consistent(run_seed, db):
    run_seed()
    projects = {p.id: p for p in db.query(models.Project).all()}
    for specimen in db.query(models.Specimen).limit(200).all():
        assert specimen.project_id in projects
        assert specimen.catalog_number.startswith(tuple(p["prefix"] for p in seed.PROJECTS))
        assert specimen.family and specimen.insect_order
    assert any(not p.finished for p in projects.values()) and any(p.finished for p in projects.values())


def test_demo_data_is_always_the_same(run_seed, db):
    run_seed()
    first = db.query(models.Specimen).order_by(models.Specimen.id).limit(20).all()
    snapshot = [(s.catalog_number, s.species, s.latitude, s.sex) for s in first]
    db.expire_all()
    run_seed("--remove")
    run_seed()
    again = db.query(models.Specimen).order_by(models.Specimen.id).limit(20).all()
    assert [(s.catalog_number, s.species, s.latitude, s.sex) for s in again] == snapshot


def test_running_the_seed_twice_does_not_duplicate(run_seed, db):
    run_seed()
    output = run_seed()
    assert "already exists" in output
    assert db.query(models.Project).count() == len(seed.PROJECTS)
    assert "0 demo specimens created" in output


def test_remove_deletes_only_the_demo_projects(run_seed, client, admin, db):
    own = client.post("/projects", json={"title": "My own project", "year": 2025, "insect_group": "G"}, headers=admin).json()
    create_specimen(client, admin, "OWN-1", project_id=own["id"])
    run_seed()
    output = run_seed("--remove")
    assert f"{len(seed.PROJECTS)} demo projects removed" in output
    assert [p.title for p in db.query(models.Project).all()] == ["My own project"]
    assert [s.catalog_number for s in db.query(models.Specimen).all()] == ["OWN-1"]


def test_missing_families_are_filled_for_known_species(run_seed, client, admin, db):
    create_specimen(client, admin, "NO-FAM", species="Dynastes hercules")
    run_seed()
    assert db.query(models.Specimen).filter_by(catalog_number="NO-FAM").one().family == "Scarabaeidae"


def test_the_demo_projects_use_the_three_visibilities(run_seed, db):
    run_seed()
    projects = db.query(models.Project).all()
    for project in projects:
        cfg = next(p for p in seed.PROJECTS if p["title"] == project.title)
        assert project.visibility == cfg.get("visibility", "public" if cfg["finished"] else "private")
        # only a link-only project has a link, and each one is different and long enough not to be guessed
        assert (project.share_token is not None) == (project.visibility == "unlisted")
    tokens = [p.share_token for p in projects if p.share_token]
    assert len(set(tokens)) == len(tokens) >= 2 and all(len(t) >= 30 for t in tokens)
    assert {p.visibility for p in projects} == {"private", "unlisted", "public"}


def test_the_seed_creates_three_laboratories_one_of_them_unlisted(run_seed, db):
    run_seed()
    labs = {lab.slug: lab for lab in db.query(models.Laboratory).all()}
    assert set(labs) == {"ufmg", "borboletas", "formigas"}
    assert (labs["ufmg"].listed, labs["borboletas"].listed, labs["formigas"].listed) == (True, True, False)
    projects_by_lab = {slug: db.query(models.Project).filter_by(laboratory_id=lab.id).count() for slug, lab in labs.items()}
    assert projects_by_lab == {"ufmg": 8, "borboletas": 3, "formigas": 1}


def test_each_specimen_belongs_to_the_laboratory_of_its_project(run_seed, db):
    run_seed()
    wrong = db.query(models.Specimen).join(models.Project, models.Specimen.project_id == models.Project.id).filter(
        models.Specimen.laboratory_id != models.Project.laboratory_id).count()
    assert wrong == 0


def test_the_same_catalog_number_is_used_in_two_laboratories(run_seed, db):
    run_seed()
    for code in ("RDO-0001", "BRI-0001"):
        owners = {s.laboratory.slug for s in db.query(models.Specimen).filter_by(catalog_number=code).all()}
        assert len(owners) == 2


def test_the_seed_creates_an_account_for_each_kind_of_person(run_seed, db):
    output = run_seed()
    users = {u.email: u for u in db.query(models.User).all()}
    assert set(users) == {u["email"] for u in seed.DEMO_USERS}
    roles = {email: {m.laboratory.slug: m.role for m in u.memberships} for email, u in users.items()}
    assert roles["super@entomobase.test"] == {} and users["super@entomobase.test"].is_superadmin
    assert roles["admin.ufmg@entomobase.test"] == {"ufmg": "admin"}
    assert roles["pesquisa.ufmg@entomobase.test"] == {"ufmg": "researcher"}
    assert roles["admin.borboletas@entomobase.test"] == {"borboletas": "admin", "ufmg": "researcher"}
    assert roles["admin.formigas@entomobase.test"] == {"formigas": "admin"}
    assert roles["sem.laboratorio@entomobase.test"] == {}
    assert sum(u.is_superadmin for u in users.values()) == 1
    assert all(u.email_verified_at is not None for u in users.values())
    assert "the passwords are shown only now" in output


def test_the_printed_passwords_work_and_are_not_stored(run_seed, client, db):
    output = run_seed()
    passwords = dict(re.findall(r"^\s+(\S+@entomobase\.test)\s+(\S+)", output, re.M))
    assert set(passwords) == {u["email"] for u in seed.DEMO_USERS}
    assert len(set(passwords.values())) == len(passwords) and all(len(p) >= 12 for p in passwords.values())
    for email, password in passwords.items():
        assert password not in db.query(models.User).filter_by(email=email).one().password_hash
    response = client.post("/login", json={"email": "admin.borboletas@entomobase.test", "password": passwords["admin.borboletas@entomobase.test"]})
    assert response.status_code == 200
    me = client.get("/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"}).json()
    assert {l["slug"]: l["role"] for l in me["laboratories"]} == {"borboletas": "admin", "ufmg": "researcher"}


def test_running_again_keeps_the_accounts_and_their_passwords(run_seed, db):
    run_seed()
    hashes = {u.email: u.password_hash for u in db.query(models.User).all()}
    output = run_seed()
    db.expire_all()
    assert {u.email: u.password_hash for u in db.query(models.User).all()} == hashes
    assert "(password unchanged)" in output and "shown only now" not in output
    assert db.query(models.Laboratory).count() == 3 and db.query(models.Membership).count() == 6


def test_remove_also_takes_the_demo_accounts_and_laboratories(run_seed, client, admin, db):
    run_seed()
    output = run_seed("--remove")
    db.expire_all()
    assert f"{len(seed.DEMO_USERS)} demo accounts removed" in output
    assert [lab.slug for lab in db.query(models.Laboratory).all()] == ["ufmg"]
    # the account of the fixture is not a demo account and stays
    assert [u.email for u in db.query(models.User).all()] == [EMAIL]
    assert db.query(models.Membership).count() == 1


def test_removing_twice_finds_nothing_left_and_does_not_fail(run_seed, db):
    run_seed()
    run_seed("--remove")
    output = run_seed("--remove")
    assert "0 demo projects removed" in output and "0 demo accounts removed" in output and "laboratory" not in output
    assert [lab.slug for lab in db.query(models.Laboratory).all()] == ["ufmg"]


def test_remove_keeps_a_demo_laboratory_that_has_other_data(run_seed, db):
    run_seed()
    formigas = db.query(models.Laboratory).filter_by(slug="formigas").one()
    db.add(models.Project(laboratory_id=formigas.id, title="Not from the seed", year=2026, insect_group="Formicidae", visibility="private", finished=False))
    db.commit()
    output = run_seed("--remove")
    db.expire_all()
    assert {lab.slug for lab in db.query(models.Laboratory).all()} == {"ufmg", "formigas"}
    assert "kept: laboratory formigas" in output and "removed: laboratory borboletas" in output


def test_remove_keeps_a_demo_laboratory_with_a_specimen_of_its_own(run_seed, db):
    run_seed()
    formigas = db.query(models.Laboratory).filter_by(slug="formigas").one()
    db.add(models.Specimen(laboratory_id=formigas.id, catalog_number="LOOSE-1", insect_order="Hymenoptera", species="Atta sexdens"))
    db.commit()
    output = run_seed("--remove")
    db.expire_all()
    assert "kept: laboratory formigas" in output
    assert db.query(models.Specimen).filter_by(catalog_number="LOOSE-1").count() == 1
