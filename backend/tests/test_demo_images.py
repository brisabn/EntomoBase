import xml.etree.ElementTree as ET

import pytest

from demo_images import render_svg

SPECIMENS = [
    ("Coleoptera", "Coccinellidae", "Coccinella septempunctata"),
    ("Coleoptera", "Scarabaeidae", "Dynastes hercules"),
    ("Coleoptera", "Scarabaeidae", "Canthon virens"),
    ("Coleoptera", "Carabidae", "Calosoma granulatum"),
    ("Coleoptera", "Chrysomelidae", "Diabrotica speciosa"),
    ("Coleoptera", "Cerambycidae", "Acrocinus longimanus"),
    ("Coleoptera", "Curculionidae", "Rhynchophorus palmarum"),
    ("Coleoptera", "Unknownidae", "Some beetle"),
    ("Lepidoptera", "Nymphalidae", "Danaus plexippus"),
    ("Lepidoptera", "Nymphalidae", "Heliconius erato"),
    ("Lepidoptera", "Nymphalidae", "Morpho helenor"),
    ("Lepidoptera", "Papilionidae", "Battus polydamas"),
    ("Lepidoptera", "Pieridae", "Phoebis sennae"),
    ("Lepidoptera", "Riodinidae", "Menander menander"),
    ("Lepidoptera", "Lycaenidae", "Some blue"),
    ("Hymenoptera", "Apidae", "Apis mellifera"),
    ("Hymenoptera", "Vespidae", "Polybia paulista"),
    ("Hymenoptera", "Formicidae", "Camponotus rufipes"),
    ("Hymenoptera", "Formicidae", "Atta sexdens"),
]


@pytest.mark.parametrize("order,family,species", SPECIMENS)
def test_every_group_produces_a_well_formed_svg(order, family, species):
    # several ids, because colors, spots and shapes are drawn at random from the id
    for specimen_id in range(1, 25):
        svg = render_svg(order, family, species, specimen_id, f"C-{specimen_id}")
        root = ET.fromstring(svg)
        assert root.tag.endswith("svg")
        assert root.get("viewBox") == "0 0 400 300"


def test_the_same_specimen_always_gets_the_same_image():
    first = render_svg("Coleoptera", "Coccinellidae", "Coccinella septempunctata", 7, "C-7")
    assert first == render_svg("Coleoptera", "Coccinellidae", "Coccinella septempunctata", 7, "C-7")


def test_different_specimens_get_different_images():
    images = {render_svg("Coleoptera", "Coccinellidae", "Coccinella septempunctata", i, f"C-{i}") for i in range(1, 11)}
    assert len(images) == 10


def test_the_label_shows_the_catalog_number():
    assert "RDO-0001" in render_svg("Coleoptera", "Carabidae", "Calosoma granulatum", 1, "RDO-0001")


def test_the_catalog_number_is_escaped():
    svg = render_svg("Coleoptera", "Carabidae", "Calosoma granulatum", 1, '<script>alert("x")</script>')
    assert "<script>" not in svg and "&lt;script&gt;" in svg
    ET.fromstring(svg)


def test_the_order_decides_the_drawing():
    beetle = render_svg("Coleoptera", "Apidae", "x", 1, "C-1")
    butterfly = render_svg("Lepidoptera", "Apidae", "x", 1, "C-1")
    bee = render_svg("Hymenoptera", "Apidae", "x", 1, "C-1")
    assert len({beetle, butterfly, bee}) == 3


def test_the_order_is_case_insensitive():
    assert render_svg("LEPIDOPTERA", "Pieridae", "x", 1, "C-1") == render_svg("lepidoptera", "Pieridae", "x", 1, "C-1")
