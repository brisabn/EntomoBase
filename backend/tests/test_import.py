import gbif
from helpers import create_project, create_specimen, error_code


def row(code, line=None, **extra):
    body = {"catalog_number": code, "insect_order": "Coleoptera", "species": "Dynastes hercules"}
    if line:
        body["line"] = line
    body.update(extra)
    return body


def post(client, admin, rows, query="dry_run=true&validate_names=false", **payload):
    return client.post(f"/specimens/import?{query}", json={"rows": rows, **payload}, headers=admin)


def codes(client, admin):
    return {s["catalog_number"] for s in client.get("/specimens", headers=admin).json()}


def test_requires_login(client):
    assert client.post("/specimens/import", json={"rows": []}).status_code == 401


def test_dry_run_counts_and_changes_nothing(client, admin):
    create_specimen(client, admin, "OLD-1")
    report = post(client, admin, [row("NEW-1"), row("NEW-2"), row("OLD-1")]).json()
    assert (report["dry_run"], report["total"], report["created"], report["updated"], report["skipped"]) == (True, 3, 2, 0, 1)
    assert report["errors"] == [] and report["warnings"] == []
    assert codes(client, admin) == {"OLD-1"}


def test_real_import_creates_specimens_with_measurements(client, admin):
    rows = [row("NEW-1", measurements=[{"trait": "Comprimento corporal", "value": 60.2, "unit": "mm"}])]
    response = post(client, admin, rows, query="validate_names=false")
    assert response.status_code == 200 and response.json()["created"] == 1
    created = client.get("/specimens", headers=admin).json()[0]
    assert created["catalog_number"] == "NEW-1" and created["measurements"][0]["value"] == 60.2


def test_rows_with_errors_block_the_whole_import(client, admin):
    rows = [row("GOOD-1"), row("BAD-1", latitude=99)]
    response = post(client, admin, rows, query="validate_names=false")
    assert response.status_code == 422
    assert error_code(response) == "import_has_errors"
    assert response.json()["detail"]["params"] == {"count": 1}
    assert codes(client, admin) == set()


def test_error_codes_per_row(client, admin):
    rows = [
        row("OK-1", line=2),
        {"line": 3, "insect_order": "C", "species": "A b"},
        row("LAT", line=4, latitude=99),
        row("OK-1", line=5),
        row("PRJ", line=6, project_id=999),
    ]
    errors = post(client, admin, rows).json()["errors"]
    by_line = {e["line"]: e for e in errors}
    assert set(by_line) == {3, 4, 5, 6}
    assert by_line[3]["problems"] == [{"code": "required", "field": "catalog_number", "params": {}}]
    assert by_line[4]["problems"][0] == {"code": "max", "field": "latitude", "params": {"limit": 90.0}}
    assert by_line[5]["problems"] == [{"code": "duplicate_in_file", "field": "catalog_number", "params": {"first_line": 2}}]
    assert by_line[5]["catalog_number"] == "OK-1"
    assert by_line[6]["problems"] == [{"code": "unknown_project", "field": "project_id", "params": {"project_id": 999}}]


def test_rows_without_a_line_are_numbered_by_position(client, admin):
    errors = post(client, admin, [row("A-1"), row("A-2", latitude=99)]).json()["errors"]
    assert errors[0]["line"] == 2


def test_catalog_numbers_are_trimmed(client, admin):
    post(client, admin, [row("  SPACE-1  ")], query="validate_names=false")
    assert codes(client, admin) == {"SPACE-1"}


def test_duplicates_are_skipped_by_default(client, admin):
    create_specimen(client, admin, "OLD-1", habitat="Cerrado")
    report = post(client, admin, [row("OLD-1", habitat="Changed")], query="validate_names=false").json()
    assert (report["created"], report["updated"], report["skipped"]) == (0, 0, 1)
    assert client.get("/specimens", headers=admin).json()[0]["habitat"] == "Cerrado"


def test_duplicates_can_update_but_never_blank_a_field(client, admin):
    create_specimen(client, admin, "OLD-1", habitat="Cerrado", family="Scarabaeidae", measurements=[{"trait": "a", "value": 1}])
    rows = [row("OLD-1", habitat="Changed", species="Megasoma actaeon")]
    report = post(client, admin, rows, query="validate_names=false", duplicates="update").json()
    assert (report["created"], report["updated"], report["skipped"]) == (0, 1, 0)
    current = client.get("/specimens", headers=admin).json()[0]
    assert current["habitat"] == "Changed" and current["species"] == "Megasoma actaeon"
    assert current["family"] == "Scarabaeidae"
    assert [m["trait"] for m in current["measurements"]] == ["a"]


def test_duplicates_update_ignores_explicit_nulls(client, admin):
    create_specimen(client, admin, "OLD-1", habitat="Cerrado", family="Scarabaeidae", notes="keep")
    rows = [row("OLD-1", habitat=None, family=None, notes="changed")]
    post(client, admin, rows, query="validate_names=false", duplicates="update")
    current = client.get("/specimens", headers=admin).json()[0]
    assert (current["habitat"], current["family"], current["notes"]) == ("Cerrado", "Scarabaeidae", "changed")


def test_duplicates_update_replaces_measurements_only_when_sent(client, admin):
    create_specimen(client, admin, "OLD-1", measurements=[{"trait": "a", "value": 1}])
    rows = [row("OLD-1", measurements=[{"trait": "b", "value": 2}])]
    post(client, admin, rows, query="validate_names=false", duplicates="update")
    assert [m["trait"] for m in client.get("/specimens", headers=admin).json()[0]["measurements"]] == ["b"]


def test_unknown_duplicates_option_is_refused(client, admin):
    assert post(client, admin, [row("A-1")], duplicates="delete").status_code == 422


def test_target_project_overrides_the_project_of_each_row(client, admin):
    project = create_project(client, admin)
    post(client, admin, [row("P-1")], query="validate_names=false", project_id=project["id"])
    assert client.get("/specimens", headers=admin).json()[0]["project_id"] == project["id"]


def test_missing_target_project(client, admin):
    response = post(client, admin, [row("P-1")], project_id=999)
    assert response.status_code == 404 and error_code(response) == "project_not_found"


def test_a_row_can_name_an_existing_project(client, admin):
    project = create_project(client, admin)
    post(client, admin, [row("P-1", project_id=project["id"])], query="validate_names=false")
    assert client.get("/specimens", headers=admin).json()[0]["project_id"] == project["id"]


def test_more_than_5000_rows_are_refused(client, admin):
    assert post(client, admin, [{} for _ in range(5001)]).status_code == 422


# ---------- GBIF warnings ----------
def fake_lookup(statuses):
    def lookup(name):
        status, suggestion = statuses.get(name, ("ok", None))
        return {"status": status, "suggestion": suggestion, "gbif_key": 1, "family": None, "order_name": None}
    return lookup


def test_warnings_only_appear_in_the_dry_run(client, admin, monkeypatch):
    monkeypatch.setattr(gbif, "lookup", fake_lookup({"Calosoma granulatum": ("synonym", "Calosoma denticolle")}))
    rows = [row("A-1", species="Calosoma granulatum"), row("A-2", species="Calosoma granulatum"), row("A-3")]
    dry = post(client, admin, rows, query="dry_run=true").json()
    assert dry["warnings"] == [{"name": "Calosoma granulatum", "kind": "synonym", "suggestion": "Calosoma denticolle", "row_count": 2}]
    real = post(client, admin, rows, query="dry_run=false").json()
    assert real["warnings"] == []


def test_warnings_never_block_the_import(client, admin, monkeypatch):
    monkeypatch.setattr(gbif, "lookup", fake_lookup({"Nonexistent name": ("not_found", None)}))
    response = post(client, admin, [row("A-1", species="Nonexistent name")], query="validate_names=true")
    assert response.status_code == 200 and response.json()["created"] == 1


def test_validate_names_false_skips_gbif(client, admin, monkeypatch):
    def forbidden(name):
        raise AssertionError("GBIF must not be called")
    monkeypatch.setattr(gbif, "lookup", forbidden)
    assert post(client, admin, [row("A-1")], query="dry_run=true&validate_names=false").json()["warnings"] == []


def test_unavailable_gbif_is_reported_once(client, admin, monkeypatch):
    monkeypatch.setattr(gbif, "lookup", fake_lookup({"Down one": ("unavailable", None)}))
    # a name with status "unavailable" in the cache path is reported as one summary warning
    monkeypatch.setattr(gbif, "validate_names", lambda names, db: {n: {"status": "unavailable", "suggestion": None, "family": None, "order_name": None} for n in names})
    warnings = post(client, admin, [row("A-1", species="Down one"), row("A-2", species="Down two")], query="dry_run=true").json()["warnings"]
    assert warnings == [{"name": "", "kind": "unavailable", "suggestion": None, "row_count": 2}]


def test_taxonomy_route_requires_login_and_returns_statuses(client, admin, monkeypatch):
    assert client.post("/taxonomy/validate", json={"names": ["A b"]}).status_code == 401
    monkeypatch.setattr(gbif, "lookup", fake_lookup({"Typo name": ("fuzzy", "Right name")}))
    response = client.post("/taxonomy/validate", json={"names": ["Typo name", "Fine name"]}, headers=admin)
    assert response.status_code == 200
    by_name = {r["name"]: r for r in response.json()}
    assert by_name["Typo name"]["status"] == "fuzzy" and by_name["Typo name"]["suggestion"] == "Right name"
    assert by_name["Fine name"]["status"] == "ok"


def test_a_file_without_a_single_valid_row_has_no_name_warnings(client, admin):
    report = post(client, admin, [{}, {"catalog_number": "X"}], query="dry_run=true&validate_names=true").json()
    assert report["created"] == 0 and len(report["errors"]) == 2 and report["warnings"] == []
