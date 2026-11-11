import csv
import io
import xml.etree.ElementTree as ET
import zipfile

import pytest

from helpers import create_project, create_specimen


def read_csv(response):
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))


@pytest.fixture
def data(client, admin):
    project = create_project(client, admin, title="Rio Doce beetles", dataset_url="https://zenodo.org/records/12345")
    create_specimen(client, admin, "A-1", project_id=project["id"], family="Scarabaeidae", latitude=-19.5, longitude=-43.5,
                    sex="macho", image_file="A 1.jpg", collection_date="2025-03-14", collector="Me",
                    measurements=[{"trait": "Comprimento corporal", "value": 60.5}, {"trait": "Chifre", "value": 12, "unit": "cm"}])
    create_specimen(client, admin, "A-2", project_id=project["id"], measurements=[{"trait": "Comprimento corporal", "value": 40}])
    # a specimen without a project is private, so it is in no public export
    create_specimen(client, admin, "OUT-1")
    return project


def test_csv_in_portuguese_is_the_default(client, data):
    default = client.get("/export/csv")
    assert default.content == client.get("/export/csv?lang=pt").content
    assert read_csv(default)[0][:6] == ["Codigo Etiqueta", "Ordem", "Familia", "Especie", "Data Coleta", "Local Coleta"]


def test_csv_in_english(client, data):
    header = read_csv(client.get("/export/csv?lang=en"))[0]
    assert header[:6] == ["Catalog Number", "Order", "Family", "Species", "Collection Date", "Locality"]
    assert "Elevation (m)" in header and "Life Stage" in header


def test_both_languages_have_the_same_rows(client, data):
    portuguese = read_csv(client.get("/export/csv?lang=pt"))
    english = read_csv(client.get("/export/csv?lang=en"))
    assert portuguese[1:] == english[1:]
    assert len(portuguese[0]) == len(english[0])


def test_full_csv_has_the_same_column_count_in_both_languages(client, admin, data):
    portuguese = read_csv(client.get("/export/csv?lang=pt&full=true", headers=admin))[0]
    english = read_csv(client.get("/export/csv?lang=en&full=true", headers=admin))[0]
    assert len(portuguese) == len(english)
    assert english[18:25] == ["Collector", "Field Number", "Storage Location", "Loan Status", "Loaned To", "Loan Date", "Internal Notes"]


def test_unknown_language_is_refused(client, data):
    assert client.get("/export/csv?lang=fr").status_code == 422


def test_file_names_follow_the_language(client, admin, data):
    disposition = lambda q, h={}: client.get(f"/export/csv?{q}", headers=h).headers["content-disposition"]
    assert "acervo_entomobase.csv" in disposition("lang=pt")
    assert "entomobase_collection.csv" in disposition("lang=en")
    assert "acervo_entomobase_completo.csv" in disposition("lang=pt&full=true", admin)
    assert "entomobase_collection_full.csv" in disposition("lang=en&full=true", admin)


def test_csv_starts_with_a_byte_order_mark_for_excel(client, data):
    assert client.get("/export/csv").content.startswith(b"\xef\xbb\xbf")


def test_one_column_per_trait_and_unit(client, data):
    rows = read_csv(client.get("/export/csv"))
    header = rows[0]
    assert header[-2:] == ["Comprimento corporal (mm)", "Chifre (cm)"]
    by_code = {r[0]: r for r in rows[1:]}
    assert by_code["A-1"][-2:] == ["60.5", "12.0"]
    assert by_code["A-2"][-2:] == ["40.0", ""]
    assert "OUT-1" not in by_code


def test_csv_can_be_limited_to_a_project(client, data):
    codes = {r[0] for r in read_csv(client.get(f"/export/csv?project_id={data['id']}"))[1:]}
    assert codes == {"A-1", "A-2"}


def test_csv_row_content(client, data):
    row = {r[0]: r for r in read_csv(client.get("/export/csv"))[1:]}["A-1"]
    assert row[1:6] == ["Coleoptera", "Scarabaeidae", "Dynastes hercules", "2025-03-14", ""]
    assert row[15] == "A 1.jpg" and row[16] == "Rio Doce beetles"


# ---------- Darwin Core ----------
def archive(client, query=""):
    return zipfile.ZipFile(io.BytesIO(client.get(f"/export/dwc{query}").content))


def test_darwin_core_archive_files(client, data):
    assert sorted(archive(client).namelist()) == ["measurementorfact.csv", "meta.xml", "occurrence.csv"]


def test_meta_xml_describes_both_tables(client, data):
    root = ET.fromstring(archive(client).read("meta.xml"))
    ns = {"d": "http://rs.tdwg.org/dwc/text/"}
    core = root.find("d:core", ns)
    extension = root.find("d:extension", ns)
    assert core.get("rowType") == "http://rs.tdwg.org/dwc/terms/Occurrence"
    assert extension.get("rowType") == "http://rs.tdwg.org/dwc/terms/MeasurementOrFact"
    header = next(csv.reader(io.StringIO(archive(client).read("occurrence.csv").decode("utf-8"))))
    terms = [f.get("term").rsplit("/", 1)[1] for f in core.findall("d:field", ns)]
    assert terms == header[1:]
    assert len(extension.findall("d:field", ns)) == 3


def test_occurrences(client, data):
    rows = list(csv.DictReader(io.StringIO(archive(client).read("occurrence.csv").decode("utf-8"))))
    by_number = {r["catalogNumber"]: r for r in rows}
    assert set(by_number) == {"A-1", "A-2"}
    first = by_number["A-1"]
    assert first["occurrenceID"] == "UFMG:EntomoBase:A-1"
    assert first["basisOfRecord"] == "PreservedSpecimen" and first["kingdom"] == "Animalia" and first["class"] == "Insecta"
    assert first["scientificName"] == "Dynastes hercules" and first["order"] == "Coleoptera"
    assert first["decimalLatitude"] == "-19.5" and first["geodeticDatum"] == "WGS84"
    assert first["datasetName"] == "Rio Doce beetles"
    assert by_number["A-2"]["geodeticDatum"] == "" and by_number["A-2"]["decimalLatitude"] == ""


def test_media_link_points_to_the_zenodo_record(client, data):
    rows = {r["catalogNumber"]: r for r in csv.DictReader(io.StringIO(archive(client).read("occurrence.csv").decode("utf-8")))}
    assert rows["A-1"]["associatedMedia"] == "https://zenodo.org/records/12345/files/A%201.jpg"
    assert rows["A-2"]["associatedMedia"] == ""


def test_demo_records_have_no_media_link(client, admin):
    project = create_project(client, admin, dataset_url="https://zenodo.org/records/0000101")
    create_specimen(client, admin, "D-1", project_id=project["id"], image_file="D-1.svg")
    rows = list(csv.DictReader(io.StringIO(archive(client).read("occurrence.csv").decode("utf-8"))))
    assert rows[0]["associatedMedia"] == ""


def test_a_photo_url_is_used_as_media(client, admin):
    project = create_project(client, admin)
    create_specimen(client, admin, "P-1", project_id=project["id"], photo_url="https://example.org/photo.jpg")
    rows = list(csv.DictReader(io.StringIO(archive(client).read("occurrence.csv").decode("utf-8"))))
    assert rows[0]["associatedMedia"] == "https://example.org/photo.jpg"


def test_measurements_table(client, data):
    rows = list(csv.DictReader(io.StringIO(archive(client).read("measurementorfact.csv").decode("utf-8"))))
    assert {(r["occurrenceID"], r["measurementType"], r["measurementValue"], r["measurementUnit"]) for r in rows} == {
        ("UFMG:EntomoBase:A-1", "Comprimento corporal", "60.5", "mm"),
        ("UFMG:EntomoBase:A-1", "Chifre", "12.0", "cm"),
        ("UFMG:EntomoBase:A-2", "Comprimento corporal", "40.0", "mm"),
    }


def test_darwin_core_can_be_limited_to_a_project(client, data):
    rows = list(csv.DictReader(io.StringIO(archive(client, f"?project_id={data['id']}").read("occurrence.csv").decode("utf-8"))))
    assert {r["catalogNumber"] for r in rows} == {"A-1", "A-2"}
