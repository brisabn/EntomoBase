import models


def add_lab(db, slug, name, listed=True):
    lab = models.Laboratory(slug=slug, name=name, institution="INST", collection_code="COL", license="http://license.test", listed=listed)
    db.add(lab)
    db.commit()
    return lab


def add_project(db, lab, visibility="public", dataset_url=None):
    project = models.Project(laboratory_id=lab.id, title="P", year=2026, insect_group="Coleoptera", visibility=visibility,
                             finished=False, dataset_url=dataset_url)
    db.add(project)
    db.commit()
    return project


def add_specimen(db, project, species, **extra):
    specimen = models.Specimen(laboratory_id=project.laboratory_id, project_id=project.id, catalog_number=f"C-{species}-{extra.pop('n', 0)}",
                               insect_order="Coleoptera", species=species, **extra)
    db.add(specimen)
    db.commit()
    return specimen


def lab_in_list(client, slug):
    return next(lab for lab in client.get("/labs").json() if lab["slug"] == slug)


# ---------- the numbers of each laboratory in the list ----------

def test_a_laboratory_counts_its_public_projects_specimens_and_species(client, db):
    lab = add_lab(db, "a", "A")
    project = add_project(db, lab)
    add_project(db, lab)
    add_specimen(db, project, "Carabus auratus", n=1)
    add_specimen(db, project, "Carabus auratus", n=2)
    add_specimen(db, project, "Cicindela campestris")
    assert {k: lab_in_list(client, "a")[k] for k in ("projects", "specimens", "species")} == {"projects": 2, "specimens": 3, "species": 2}


def test_private_and_link_only_projects_are_not_counted(client, db):
    lab = add_lab(db, "a", "A")
    for visibility in ("private", "unlisted"):
        add_specimen(db, add_project(db, lab, visibility=visibility), "Hidden " + visibility)
    assert {k: lab_in_list(client, "a")[k] for k in ("projects", "specimens", "species")} == {"projects": 0, "specimens": 0, "species": 0}


def test_a_specimen_without_a_project_is_not_counted(client, db):
    lab = add_lab(db, "a", "A")
    db.add(models.Specimen(laboratory_id=lab.id, catalog_number="X", insect_order="Coleoptera", species="Loose one"))
    db.commit()
    assert lab_in_list(client, "a")["specimens"] == 0


def test_each_laboratory_counts_only_its_own(client, db):
    a, b = add_lab(db, "a", "A"), add_lab(db, "b", "B")
    add_specimen(db, add_project(db, a), "Only in A")
    pb = add_project(db, b)
    add_specimen(db, pb, "In B", n=1)
    add_specimen(db, pb, "In B", n=2)
    assert lab_in_list(client, "a")["specimens"] == 1 and lab_in_list(client, "b")["specimens"] == 2
    assert lab_in_list(client, "a")["projects"] == 1 and lab_in_list(client, "b")["projects"] == 1


def test_an_unlisted_laboratory_with_public_data_does_not_disturb_the_list(client, db):
    listed, unlisted = add_lab(db, "a", "A"), add_lab(db, "z", "Z", listed=False)
    add_specimen(db, add_project(db, listed), "In A")
    add_specimen(db, add_project(db, unlisted), "In Z")
    response = client.get("/labs")
    assert response.status_code == 200 and [(lab["slug"], lab["specimens"]) for lab in response.json()] == [("a", 1)]


# ---------- the picture on the card ----------

def test_the_cover_is_the_newest_public_specimen_with_a_photo(client, db):
    lab = add_lab(db, "a", "A")
    project = add_project(db, lab)
    add_specimen(db, project, "Old", photo_url="https://img.test/old.jpg")
    newest = add_specimen(db, project, "New", photo_url="https://img.test/new.jpg")
    add_specimen(db, project, "No photo")
    assert lab_in_list(client, "a")["cover"] == {"specimen_id": newest.id, "photo_url": "https://img.test/new.jpg",
                                                 "image_file": None, "dataset_url": None}


def test_a_file_counts_as_a_picture_only_with_the_repository_of_its_project(client, db):
    lab = add_lab(db, "a", "A")
    add_specimen(db, add_project(db, lab), "No repository", image_file="a.jpg")
    assert lab_in_list(client, "a")["cover"] is None
    with_repository = add_specimen(db, add_project(db, lab, dataset_url="https://zenodo.org/records/1"), "Stored", image_file="b.jpg")
    assert lab_in_list(client, "a")["cover"] == {"specimen_id": with_repository.id, "photo_url": None, "image_file": "b.jpg",
                                                 "dataset_url": "https://zenodo.org/records/1"}


def test_an_empty_file_name_is_no_picture(client, db):
    lab = add_lab(db, "a", "A")
    add_specimen(db, add_project(db, lab, dataset_url="https://zenodo.org/records/1"), "Blank", image_file="")
    assert lab_in_list(client, "a")["cover"] is None


def test_a_photo_field_that_is_not_an_address_is_no_picture(client, db):
    lab = add_lab(db, "a", "A")
    add_specimen(db, add_project(db, lab), "Odd", photo_url="see drawer 3")
    assert lab_in_list(client, "a")["cover"] is None


def test_the_cover_never_comes_from_a_hidden_project(client, db):
    lab = add_lab(db, "a", "A")
    for visibility in ("private", "unlisted"):
        add_specimen(db, add_project(db, lab, visibility=visibility, dataset_url="https://zenodo.org/records/1"), visibility,
                     photo_url="https://img.test/secret.jpg", image_file="secret.jpg")
    assert lab_in_list(client, "a")["cover"] is None


def test_the_cover_never_comes_from_another_laboratory(client, db):
    a, b = add_lab(db, "a", "A"), add_lab(db, "b", "B")
    add_project(db, a)
    add_specimen(db, add_project(db, b), "B's", photo_url="https://img.test/b.jpg")
    assert lab_in_list(client, "a")["cover"] is None


# ---------- the numbers of the platform ----------

def test_the_platform_numbers_add_up_the_listed_laboratories(client, db):
    a, b = add_lab(db, "a", "A"), add_lab(db, "b", "B")
    pa = add_project(db, a)
    add_specimen(db, pa, "Carabus auratus", n=1)
    add_specimen(db, pa, "Shared species", n=1)
    pb = add_project(db, b)
    add_project(db, b)
    add_specimen(db, pb, "Shared species", n=2)
    assert client.get("/overview").json() == {"laboratories": 2, "projects": 3, "specimens": 3, "species": 2}


def test_the_platform_numbers_leave_out_hidden_projects_and_unlisted_laboratories(client, db):
    listed, unlisted = add_lab(db, "a", "A"), add_lab(db, "z", "Z", listed=False)
    add_specimen(db, add_project(db, listed, visibility="private"), "Private one")
    add_specimen(db, add_project(db, listed, visibility="unlisted"), "Link-only one")
    add_specimen(db, add_project(db, unlisted), "In an unlisted laboratory")
    assert client.get("/overview").json() == {"laboratories": 1, "projects": 0, "specimens": 0, "species": 0}


def test_the_platform_numbers_start_at_zero(client, db):
    assert client.get("/overview").json() == {"laboratories": 0, "projects": 0, "specimens": 0, "species": 0}


def test_the_numbers_need_no_login_and_ignore_a_bad_token(client, db):
    add_specimen(db, add_project(db, add_lab(db, "a", "A")), "Carabus auratus")
    bad = {"Authorization": "Bearer garbage"}
    assert client.get("/overview", headers=bad).json()["specimens"] == 1
    assert client.get("/labs", headers=bad).json()[0]["specimens"] == 1
