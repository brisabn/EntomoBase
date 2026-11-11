import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models

MATCH_URL = "https://api.gbif.org/v1/species/match"
TAXON_URL = "https://api.gbif.org/v1/species/"
CACHE_TTL = timedelta(days=30)
REQUEST_TIMEOUT = 6
# maximum total time per batch; whatever is left is reported as not checked
BATCH_BUDGET_SECONDS = 25

# possible statuses: ok, fuzzy, synonym, genus_only, not_found, unavailable
CACHEABLE_STATUSES = {"ok", "fuzzy", "synonym", "genus_only", "not_found"}


def _get(url: str, params: dict | None = None) -> dict:
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "EntomoBase/0.4"})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def _canonical(name: str) -> str:
    # compares only genus and epithet, ignoring author, year and case
    parts = re.sub(r"[()]", " ", name or "").split()
    return " ".join(parts[:2]).lower() if len(parts) >= 2 else " ".join(parts).lower()


def _unavailable() -> dict:
    return {"status": "unavailable", "suggestion": None, "family": None, "order_name": None}


# does the real GBIF lookup; kept separate so tests can replace it
def lookup(name: str) -> dict:
    data = _get(MATCH_URL, {"name": name, "kingdom": "Animalia", "class": "Insecta"})
    match_type = data.get("matchType", "NONE")
    canonical = data.get("canonicalName") or data.get("scientificName")
    result = {
        "gbif_key": data.get("usageKey"),
        "family": data.get("family"),
        "order_name": data.get("order"),
        "suggestion": None,
    }
    if match_type == "NONE" or not canonical:
        result["status"] = "not_found"
        return result
    if match_type == "HIGHERRANK":
        result["status"] = "genus_only"
        result["suggestion"] = canonical
        return result
    if data.get("status") == "SYNONYM" or data.get("synonym"):
        accepted = canonical
        key = data.get("acceptedUsageKey")
        if key:
            try:
                detail = _get(TAXON_URL + str(key))
                accepted = detail.get("canonicalName") or detail.get("scientificName") or canonical
                result["family"] = detail.get("family") or result["family"]
                result["order_name"] = detail.get("order") or result["order_name"]
            except (urllib.error.URLError, TimeoutError, ValueError):
                pass
        result["status"] = "synonym"
        result["suggestion"] = accepted
        return result
    if match_type in ("FUZZY", "VARIANT") or _canonical(canonical) != _canonical(name):
        result["status"] = "fuzzy"
        result["suggestion"] = canonical
        return result
    result["status"] = "ok"
    return result


def validate_names(names: list[str], db: Session) -> dict[str, dict]:
    output = {}
    unique = []
    for n in names:
        n = (n or "").strip()
        if n and n not in output and n not in unique:
            unique.append(n)

    # stored without timezone, as the column is a plain DateTime
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cached = {
        t.queried_name: t
        for t in db.query(models.Taxon).filter(models.Taxon.queried_name.in_(unique)).all()
    } if unique else {}

    gbif_down = False
    start = time.monotonic()
    for name in unique:
        t = cached.get(name)
        if t is not None and now - t.queried_at < CACHE_TTL:
            output[name] = {"status": t.status, "suggestion": t.suggestion, "family": t.family, "order_name": t.order_name}
            continue
        if gbif_down or time.monotonic() - start > BATCH_BUDGET_SECONDS:
            output[name] = _unavailable()
            continue
        try:
            r = lookup(name)
        except urllib.error.HTTPError as error:
            # a 4xx error is a problem with this name; only a server failure stops the batch
            gbif_down = error.code >= 500
            output[name] = _unavailable()
            continue
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            # if GBIF does not answer, the rest of the list is not even tried
            gbif_down = True
            output[name] = _unavailable()
            continue
        if t is None:
            t = models.Taxon(queried_name=name)
            db.add(t)
        t.status = r["status"]
        t.suggestion = r["suggestion"]
        t.gbif_key = r["gbif_key"]
        t.family = r["family"]
        t.order_name = r["order_name"]
        t.queried_at = now
        output[name] = {k: r[k] for k in ("status", "suggestion", "family", "order_name")}
    try:
        db.commit()
    except IntegrityError:
        # another request cached the same name at the same time and its rows were kept;
        # the cache is only an optimization, so these results are still returned
        db.rollback()
    return output
