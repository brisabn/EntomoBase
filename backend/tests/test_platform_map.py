import models
import platform_map
from tests.test_public_numbers import add_lab, add_project, add_specimen


def place(db, project, species, lat=-19.9, lon=-43.9, **extra):
    return add_specimen(db, project, species, latitude=lat, longitude=lon, **extra)


def test_a_public_specimen_with_coordinates_is_a_point_with_its_laboratory(client, db):
    lab = add_lab(db, "a", "Lab A")
    specimen = place(db, add_project(db, lab, dataset_url="https://zenodo.org/records/1"), "Carabus auratus",
                     locality="Serra", image_file="c.jpg", photo_url="https://img.test/c.jpg")
    assert client.get("/map").json() == [{
        "id": specimen.id, "catalog_number": specimen.catalog_number, "species": "Carabus auratus", "insect_order": "Coleoptera",
        "locality": "Serra", "latitude": -19.9, "longitude": -43.9, "photo_url": "https://img.test/c.jpg", "image_file": "c.jpg",
        "dataset_url": "https://zenodo.org/records/1", "laboratory": "a", "laboratory_name": "Lab A",
    }]


def test_internal_fields_are_never_sent(client, db):
    place(db, add_project(db, add_lab(db, "a", "A")), "Carabus auratus", collector="Secret Person", storage_location="Drawer 9",
          internal_notes="do not share", loaned_to="Someone")
    body = client.get("/map").text
    assert all(secret not in body for secret in ("Secret Person", "Drawer 9", "do not share", "Someone"))


def test_specimens_without_both_coordinates_are_left_out(client, db):
    project = add_project(db, add_lab(db, "a", "A"))
    add_specimen(db, project, "No coordinates")
    add_specimen(db, project, "Only latitude", latitude=-10.0)
    add_specimen(db, project, "Only longitude", longitude=-40.0)
    place(db, project, "Placed")
    assert [p["species"] for p in client.get("/map").json()] == ["Placed"]


def test_a_point_at_zero_zero_is_kept(client, db):
    place(db, add_project(db, add_lab(db, "a", "A")), "On the equator", lat=0.0, lon=0.0)
    assert [(p["latitude"], p["longitude"]) for p in client.get("/map").json()] == [(0.0, 0.0)]


def test_hidden_projects_and_loose_specimens_are_left_out(client, db):
    lab = add_lab(db, "a", "A")
    for visibility in ("private", "unlisted"):
        place(db, add_project(db, lab, visibility=visibility), "Hidden " + visibility)
    db.add(models.Specimen(laboratory_id=lab.id, catalog_number="L", insect_order="Coleoptera", species="Loose", latitude=1.0, longitude=1.0))
    db.commit()
    assert client.get("/map").json() == []


def test_unlisted_laboratories_are_left_out(client, db):
    place(db, add_project(db, add_lab(db, "z", "Z", listed=False)), "In Z")
    place(db, add_project(db, add_lab(db, "a", "A")), "In A")
    assert [(p["laboratory"], p["species"]) for p in client.get("/map").json()] == [("a", "In A")]


def test_points_of_several_laboratories_come_together_newest_first(client, db):
    a, b = add_lab(db, "a", "A"), add_lab(db, "b", "B")
    place(db, add_project(db, a), "First")
    place(db, add_project(db, b), "Second")
    place(db, add_project(db, a), "Third")
    assert [(p["laboratory"], p["species"]) for p in client.get("/map").json()] == [("a", "Third"), ("b", "Second"), ("a", "First")]


def test_the_answer_is_capped_keeping_the_newest(client, db):
    project = add_project(db, add_lab(db, "a", "A"))
    for n in range(4):
        place(db, project, f"S{n}")
    assert [p["species"] for p in platform_map.map_points(db, limit=2)] == ["S3", "S2"]
    assert platform_map.MAX_POINTS == 5000


def test_the_map_needs_no_login_and_ignores_a_bad_token(client, db):
    place(db, add_project(db, add_lab(db, "a", "A")), "Carabus auratus")
    assert len(client.get("/map", headers={"Authorization": "Bearer garbage"}).json()) == 1
