import urllib.error
from datetime import datetime, timedelta, timezone

import pytest

import gbif
import models
from database import SessionLocal


def match(match_type="EXACT", canonical="Dynastes hercules", **extra):
    return {"matchType": match_type, "canonicalName": canonical, "usageKey": 111, "family": "Scarabaeidae",
            "order": "Coleoptera", "status": "ACCEPTED", **extra}


# the real lookup(), captured before the tests replace it; only the HTTP call is faked
REAL_LOOKUP = gbif.lookup


def real(monkeypatch, answers, name):
    def fake_get(url, params=None):
        value = answers[url if params is None else params["name"]]
        if isinstance(value, Exception):
            raise value
        return value
    monkeypatch.setattr(gbif, "_get", fake_get)
    return REAL_LOOKUP(name)


# ---------- mapping of the GBIF answer ----------
def test_exact_match_is_ok_and_carries_family_and_order(monkeypatch):
    result = real(monkeypatch, {"Dynastes hercules": match()}, "Dynastes hercules")
    assert result["status"] == "ok" and result["suggestion"] is None
    assert (result["family"], result["order_name"], result["gbif_key"]) == ("Scarabaeidae", "Coleoptera", 111)


def test_author_and_case_are_ignored(monkeypatch):
    name = "dynastes HERCULES (Linnaeus, 1758)"
    assert real(monkeypatch, {name: match()}, name)["status"] == "ok"


def test_fuzzy_match_suggests_the_canonical_name(monkeypatch):
    result = real(monkeypatch, {"Dynastes hercules": match("FUZZY", "Dynastes hercules")}, "Dynastes hercules")
    assert (result["status"], result["suggestion"]) == ("fuzzy", "Dynastes hercules")


def test_a_different_name_is_reported_as_fuzzy_even_when_gbif_says_exact(monkeypatch):
    result = real(monkeypatch, {"Dynastes tityus": match("EXACT", "Dynastes hercules")}, "Dynastes tityus")
    assert (result["status"], result["suggestion"]) == ("fuzzy", "Dynastes hercules")


def test_genus_only(monkeypatch):
    result = real(monkeypatch, {"Dynastes zzz": match("HIGHERRANK", "Dynastes")}, "Dynastes zzz")
    assert (result["status"], result["suggestion"]) == ("genus_only", "Dynastes")


def test_not_found(monkeypatch):
    assert real(monkeypatch, {"Asdf qwer": {"matchType": "NONE"}}, "Asdf qwer")["status"] == "not_found"


def test_synonym_suggests_the_accepted_name(monkeypatch):
    answers = {
        "Calosoma granulatum": match("EXACT", "Calosoma granulatum", status="SYNONYM", acceptedUsageKey=222),
        "https://api.gbif.org/v1/species/222": {"canonicalName": "Calosoma denticolle", "family": "Carabidae", "order": "Coleoptera"},
    }
    result = real(monkeypatch, answers, "Calosoma granulatum")
    assert (result["status"], result["suggestion"], result["family"]) == ("synonym", "Calosoma denticolle", "Carabidae")


def test_synonym_still_works_when_the_accepted_name_cannot_be_fetched(monkeypatch):
    answers = {
        "Calosoma granulatum": match("EXACT", "Calosoma granulatum", status="SYNONYM", acceptedUsageKey=222),
        "https://api.gbif.org/v1/species/222": urllib.error.URLError("down"),
    }
    result = real(monkeypatch, answers, "Calosoma granulatum")
    assert (result["status"], result["suggestion"]) == ("synonym", "Calosoma granulatum")


# ---------- validate_names: cache and failures ----------
@pytest.fixture
def counted(monkeypatch):
    calls = []

    def lookup(name):
        calls.append(name)
        return {"status": "ok", "suggestion": None, "gbif_key": 1, "family": "F", "order_name": "O"}
    monkeypatch.setattr(gbif, "lookup", lookup)
    return calls


def test_blank_and_repeated_names_are_ignored(db, counted):
    result = gbif.validate_names(["A b", "", "  ", "A b", None, "C d"], db)
    assert set(result) == {"A b", "C d"} and counted == ["A b", "C d"]


def test_results_are_cached(db, counted):
    gbif.validate_names(["A b"], db)
    again = gbif.validate_names(["A b"], db)
    assert counted == ["A b"]
    assert again["A b"] == {"status": "ok", "suggestion": None, "family": "F", "order_name": "O"}
    assert db.query(models.Taxon).count() == 1


def test_an_old_cache_entry_is_looked_up_again(db, counted):
    gbif.validate_names(["A b"], db)
    taxon = db.query(models.Taxon).one()
    taxon.queried_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=31)
    db.commit()
    gbif.validate_names(["A b"], db)
    assert counted == ["A b", "A b"]
    assert db.query(models.Taxon).count() == 1


def test_a_recent_cache_entry_is_not_looked_up_again(db, counted):
    gbif.validate_names(["A b"], db)
    taxon = db.query(models.Taxon).one()
    taxon.queried_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=29)
    db.commit()
    gbif.validate_names(["A b"], db)
    assert counted == ["A b"]


def test_a_network_failure_stops_the_batch_and_is_not_cached(db, monkeypatch):
    calls = []

    def lookup(name):
        calls.append(name)
        raise urllib.error.URLError("down")
    monkeypatch.setattr(gbif, "lookup", lookup)
    result = gbif.validate_names(["A b", "C d", "E f"], db)
    assert calls == ["A b"]
    assert {r["status"] for r in result.values()} == {"unavailable"}
    assert db.query(models.Taxon).count() == 0


def test_a_server_error_stops_the_batch(db, monkeypatch):
    calls = []

    def lookup(name):
        calls.append(name)
        raise urllib.error.HTTPError("u", 503, "unavailable", {}, None)
    monkeypatch.setattr(gbif, "lookup", lookup)
    result = gbif.validate_names(["A b", "C d"], db)
    assert calls == ["A b"] and {r["status"] for r in result.values()} == {"unavailable"}


def test_a_client_error_only_affects_that_name(db, monkeypatch):
    def lookup(name):
        if name == "Bad name":
            raise urllib.error.HTTPError("u", 400, "bad request", {}, None)
        return {"status": "ok", "suggestion": None, "gbif_key": 1, "family": None, "order_name": None}
    monkeypatch.setattr(gbif, "lookup", lookup)
    result = gbif.validate_names(["Bad name", "Good name"], db)
    assert result["Bad name"]["status"] == "unavailable" and result["Good name"]["status"] == "ok"


def test_the_time_budget_leaves_the_rest_unchecked(db, counted, monkeypatch):
    monkeypatch.setattr(gbif, "BATCH_BUDGET_SECONDS", -1)
    result = gbif.validate_names(["A b", "C d"], db)
    assert counted == [] and {r["status"] for r in result.values()} == {"unavailable"}


def test_two_requests_caching_the_same_name_do_not_fail(db, monkeypatch):
    # while this request looks the name up, another request caches it first
    def lookup(name):
        other = SessionLocal()
        other.add(models.Taxon(queried_name=name, status="ok", queried_at=datetime.now(timezone.utc).replace(tzinfo=None)))
        other.commit()
        other.close()
        return {"status": "ok", "suggestion": None, "gbif_key": 1, "family": None, "order_name": None}
    monkeypatch.setattr(gbif, "lookup", lookup)
    result = gbif.validate_names(["A b"], db)
    assert result["A b"]["status"] == "ok"
    assert db.query(models.Taxon).count() == 1


# ---------- the real HTTP call ----------
REAL_GET = gbif._get


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_get_builds_the_url_sends_the_headers_and_parses_json(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"], seen["headers"], seen["timeout"] = request.full_url, dict(request.header_items()), timeout
        return FakeResponse('{"canonicalName": "Dynastes hercules"}'.encode("utf-8"))
    monkeypatch.setattr(gbif.urllib.request, "urlopen", fake_urlopen)
    result = REAL_GET("https://api.gbif.org/v1/species/match", {"name": "Dynastes hercules", "class": "Insecta"})
    assert result == {"canonicalName": "Dynastes hercules"}
    assert seen["url"] == "https://api.gbif.org/v1/species/match?name=Dynastes+hercules&class=Insecta"
    assert seen["headers"]["Accept"] == "application/json" and seen["headers"]["User-agent"].startswith("EntomoBase")
    assert seen["timeout"] == gbif.REQUEST_TIMEOUT


def test_get_without_parameters_uses_the_url_as_is(monkeypatch):
    seen = {}
    monkeypatch.setattr(gbif.urllib.request, "urlopen", lambda request, timeout: seen.update(url=request.full_url) or FakeResponse(b"{}"))
    assert REAL_GET("https://api.gbif.org/v1/species/222") == {}
    assert seen["url"] == "https://api.gbif.org/v1/species/222"
