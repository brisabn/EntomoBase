import sys

import pytest

import models
import seed
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


def test_finished_demo_projects_are_public_and_the_others_private(run_seed, db):
    run_seed()
    for project in db.query(models.Project).all():
        assert project.visibility == ("public" if project.finished else "private")
        assert project.share_token is None
    assert {p.laboratory_id for p in db.query(models.Project).all()} == {db.query(models.Laboratory).one().id}
