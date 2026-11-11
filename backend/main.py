import csv
import io
import os
import re
import secrets
import urllib.parse
import zipfile
import jwt
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from fastapi.responses import JSONResponse, StreamingResponse, Response
from fastapi import FastAPI, Depends, HTTPException, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional

import gbif
import models
import schemas
from database import get_db
from db_setup import initialize_database
from demo_images import render_svg
from rate_limit import AttemptLimiter
from security import hash_password, needs_rehash, verify_password

# errors are sent as {"detail": {"code": ..., "params": {...}}}; the site turns the code into a message
# in its own language. Exported file contents stay in Portuguese: they are shown to the site's users


def api_error(status_code: int, code: str, headers: Optional[dict] = None, **params) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "params": params}, headers=headers)


# pydantic error types the site has a message for; any other type is shown as an invalid value
VALIDATION_CODES = {"missing": "required", "less_than_equal": "max", "greater_than_equal": "min", "string_too_short": "empty"}


def problems_from(errors) -> List[dict]:
    problems = []
    for e in errors:
        loc = [str(p) for p in e.get("loc", ())]
        if loc and loc[0] in ("body", "query", "path"):
            loc = loc[1:]
        ctx = e.get("ctx") or {}
        limit = ctx.get("le", ctx.get("ge"))
        problems.append({
            "code": VALIDATION_CODES.get(e.get("type"), "invalid_value"),
            "field": ".".join(loc) or None,
            "params": {"limit": limit} if limit is not None else {},
        })
    return problems


# the database is prepared when the API starts, not when this file is imported
@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="EntomoBase API", version="0.4.0", lifespan=lifespan)


# invalid request bodies use the same format as the other errors
@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": {"code": "invalid_request", "params": {}, "problems": problems_from(exc.errors())}})

# origins allowed to call the API from a browser, read from CORS_ORIGINS (comma separated)
# in dev mode, without the variable, the frontend address from the README is allowed
DEV_ORIGINS = ["http://127.0.0.1:5500", "http://localhost:5500"]


def load_allowed_origins() -> List[str]:
    raw = os.getenv("CORS_ORIGINS", "")
    origins = [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    if origins:
        return origins
    if os.getenv("ENTOMOBASE_ENV") == "dev":
        return DEV_ORIGINS
    print("WARNING: CORS_ORIGINS is not set; no site from another origin will be able to use the API.")
    return []


# login uses the Authorization header (Bearer), not cookies, so there are no browser credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=load_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# --- JWT security settings ---
ALGORITHM = "HS256"


# the key comes from the environment; without it the API only starts in development mode (ENTOMOBASE_ENV=dev),
# with a random key that changes on every start and invalidates previous logins
def load_secret_key() -> str:
    key = os.getenv("SECRET_KEY")
    if key:
        return key
    if os.getenv("ENTOMOBASE_ENV") == "dev":
        print("WARNING: SECRET_KEY is not set; using a temporary key (dev mode).")
        return secrets.token_urlsafe(32)
    raise RuntimeError(
        "SECRET_KEY is not set. Set the SECRET_KEY environment variable, "
        "or use ENTOMOBASE_ENV=dev only in development."
    )


SECRET_KEY = load_secret_key()


def require_login(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise api_error(401, "missing_token")
    token = authorization.split(" ")[1]
    try:
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise api_error(401, "session_expired")


# does not require login; only tells whether the token sent is valid
def is_logged_in(authorization: str = Header(None)) -> bool:
    if not authorization or not authorization.startswith("Bearer "):
        return False
    try:
        jwt.decode(authorization.split(" ")[1], SECRET_KEY, algorithms=[ALGORITHM])
        return True
    except jwt.PyJWTError:
        return False


# --- Authentication ---
# limits on wrong passwords per 15-minute window: per account (email + IP) and per IP overall
LOGIN_WINDOW_SECONDS = 15 * 60
account_limiter = AttemptLimiter(max_attempts=5, window_seconds=LOGIN_WINDOW_SECONDS)
ip_limiter = AttemptLimiter(max_attempts=20, window_seconds=LOGIN_WINDOW_SECONDS)


def ensure_login_allowed(*limiters_and_keys):
    wait = max((limiter.seconds_remaining(key) for limiter, key in limiters_and_keys), default=0)
    if wait:
        minutes = (wait + 59) // 60
        raise api_error(429, "too_many_attempts", headers={"Retry-After": str(wait)}, minutes=minutes)


# there is no default user: the first one is created with `python create_admin.py email@example.com`
@app.post("/login")
def login(credentials: schemas.UserLogin, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    email = credentials.email.strip().lower()
    account_key = (ip, email)
    # blocked attempts do not even check the password, which also spares argon2, slow on purpose
    ensure_login_allowed((account_limiter, account_key), (ip_limiter, ip))

    user = db.query(models.User).filter(func.lower(models.User.email) == email).first()
    if not verify_password(credentials.password, user.password_hash if user else None):
        account_limiter.record_failure(account_key)
        ip_limiter.record_failure(ip)
        raise api_error(401, "invalid_credentials")
    account_limiter.reset(account_key)
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(credentials.password)
        db.commit()

    exp = datetime.now(timezone.utc) + timedelta(hours=8)
    token = jwt.encode({"sub": user.email, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "email": user.email}


# --- Project routes ---
@app.post("/projects", response_model=schemas.ProjectResponse, status_code=201)
def create_project(project: schemas.ProjectCreate, db: Session = Depends(get_db), auth: None = Depends(require_login)):
    db_project = models.Project(**project.model_dump())
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


@app.get("/projects", response_model=List[schemas.ProjectResponse])
def list_projects(
    year: Optional[int] = None, insect_group: Optional[str] = None,
    locality: Optional[str] = None, finished: Optional[bool] = None,
    logged_in: bool = Depends(is_logged_in), db: Session = Depends(get_db)
):
    query = db.query(models.Project)
    # visitors only see finished projects; the token is really verified
    if not logged_in:
        query = query.filter(models.Project.finished == True)
    elif finished is not None:
        query = query.filter(models.Project.finished == finished)
    if year: query = query.filter(models.Project.year == year)
    if insect_group: query = query.filter(models.Project.insect_group.ilike(f"%{insect_group}%"))
    if locality: query = query.filter(models.Project.locality.ilike(f"%{locality}%"))
    return query.order_by(models.Project.year.desc(), models.Project.id).all()


@app.put("/projects/{project_id}", response_model=schemas.ProjectResponse)
def update_project(project_id: int, data: schemas.ProjectUpdate, db: Session = Depends(get_db), auth: None = Depends(require_login)):
    db_project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not db_project: raise api_error(404, "project_not_found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(db_project, key, value)
    db.commit()
    db.refresh(db_project)
    return db_project


@app.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db), auth: None = Depends(require_login)):
    db_project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not db_project: raise api_error(404, "project_not_found")
    db.delete(db_project)
    db.commit()
    return None


# --- Specimen routes ---
def filter_visible(query, logged_in: bool):
    # visitors do not see specimens from projects still in progress
    if logged_in:
        return query
    return query.outerjoin(models.Project, models.Specimen.project_id == models.Project.id).filter(
        or_(models.Specimen.project_id.is_(None), models.Project.finished == True)
    )


# visitors receive the specimen without the internal fields; they are removed here, on the server
def specimen_output(specimen: models.Specimen, logged_in: bool) -> dict:
    exclude = None if logged_in else schemas.INTERNAL_FIELDS
    return schemas.SpecimenResponse.model_validate(specimen).model_dump(mode="json", exclude=exclude)


def replace_measurements(specimen: models.Specimen, measurements):
    specimen.measurements.clear()
    for m in measurements:
        specimen.measurements.append(models.Measurement(**m.model_dump()))


@app.post("/specimens", response_model=schemas.SpecimenResponse, status_code=201)
def create_specimen(specimen: schemas.SpecimenCreate, db: Session = Depends(get_db), auth: None = Depends(require_login)):
    if db.query(models.Specimen).filter(models.Specimen.catalog_number == specimen.catalog_number).first():
        raise api_error(400, "duplicate_catalog_number")
    db_specimen = models.Specimen(**specimen.model_dump(exclude={"measurements"}))
    replace_measurements(db_specimen, specimen.measurements or [])
    db.add(db_specimen)
    db.commit()
    db.refresh(db_specimen)
    return db_specimen


@app.get("/specimens")
def list_specimens(
    species: Optional[str] = None, project_id: Optional[int] = None,
    logged_in: bool = Depends(is_logged_in), db: Session = Depends(get_db)
):
    query = filter_visible(db.query(models.Specimen), logged_in).options(selectinload(models.Specimen.measurements))
    if species: query = query.filter(models.Specimen.species.ilike(f"%{species}%"))
    if project_id: query = query.filter(models.Specimen.project_id == project_id)
    specimens = query.order_by(models.Specimen.insect_order, models.Specimen.species, models.Specimen.catalog_number).all()
    return [specimen_output(s, logged_in) for s in specimens]


@app.put("/specimens/{specimen_id}", response_model=schemas.SpecimenResponse)
def update_specimen(specimen_id: int, data: schemas.SpecimenUpdate, db: Session = Depends(get_db), auth: None = Depends(require_login)):
    specimen = db.query(models.Specimen).filter(models.Specimen.id == specimen_id).first()
    if not specimen: raise api_error(404, "specimen_not_found")

    required = {"catalog_number", "insect_order", "species"}
    fields = {
        k: v for k, v in data.model_dump(exclude_unset=True, exclude={"measurements"}).items()
        if not (v is None and k in required)
    }
    new_number = fields.get("catalog_number")
    if new_number and new_number != specimen.catalog_number:
        if db.query(models.Specimen).filter(models.Specimen.catalog_number == new_number).first():
            raise api_error(400, "duplicate_catalog_number")
    for key, value in fields.items():
        setattr(specimen, key, value)

    # measurements sent replace the previous ones; if none are sent, they stay as they are
    if data.measurements is not None:
        replace_measurements(specimen, data.measurements)
    db.commit()
    db.refresh(specimen)
    return specimen


@app.delete("/specimens/{specimen_id}", status_code=204)
def delete_specimen(specimen_id: int, db: Session = Depends(get_db), auth: None = Depends(require_login)):
    specimen = db.query(models.Specimen).filter(models.Specimen.id == specimen_id).first()
    if not specimen: raise api_error(404, "specimen_not_found")
    db.delete(specimen)
    db.commit()
    return None


# --- Bulk import ---


@app.post("/specimens/import", response_model=schemas.ImportReport)
def import_specimens(
    payload: schemas.ImportRequest, dry_run: bool = False, validate_names: bool = True,
    db: Session = Depends(get_db), auth: None = Depends(require_login)
):
    if payload.project_id is not None:
        if not db.query(models.Project).filter(models.Project.id == payload.project_id).first():
            raise api_error(404, "project_not_found")

    project_ids = {p.id for p in db.query(models.Project.id).all()}
    errors = []
    valid = []
    seen = {}
    for position, raw in enumerate(payload.rows, start=1):
        line = raw.get("line") or position
        try:
            item = schemas.SpecimenCreate(**raw)
        except ValidationError as e:
            errors.append(schemas.ImportRowError(line=line, catalog_number=str(raw.get("catalog_number") or ""), problems=problems_from(e.errors())))
            continue
        item.catalog_number = item.catalog_number.strip()
        if payload.project_id is not None:
            item.project_id = payload.project_id
        elif item.project_id is not None and item.project_id not in project_ids:
            errors.append(schemas.ImportRowError(line=line, catalog_number=item.catalog_number, problems=[schemas.Problem(code="unknown_project", field="project_id", params={"project_id": item.project_id})]))
            continue
        if item.catalog_number in seen:
            errors.append(schemas.ImportRowError(line=line, catalog_number=item.catalog_number, problems=[schemas.Problem(code="duplicate_in_file", field="catalog_number", params={"first_line": seen[item.catalog_number]})]))
            continue
        seen[item.catalog_number] = line
        valid.append((line, item))

    existing = {}
    numbers = list(seen.keys())
    for i in range(0, len(numbers), 500):
        for s in db.query(models.Specimen).filter(models.Specimen.catalog_number.in_(numbers[i:i + 500])).all():
            existing[s.catalog_number] = s

    created = updated = skipped = 0
    for line, item in valid:
        current = existing.get(item.catalog_number)
        if current is None:
            created += 1
            if not dry_run and not errors:
                new = models.Specimen(**item.model_dump(exclude={"measurements"}))
                replace_measurements(new, item.measurements or [])
                db.add(new)
        elif payload.duplicates == "update":
            updated += 1
            if not dry_run and not errors:
                for k, v in item.model_dump(exclude_unset=True, exclude={"measurements", "catalog_number"}).items():
                    if v is not None:
                        setattr(current, k, v)
                if item.measurements:
                    replace_measurements(current, item.measurements)
        else:
            skipped += 1

    if not dry_run:
        if errors:
            db.rollback()
            raise api_error(422, "import_has_errors", count=len(errors))
        db.commit()

    warnings = taxonomy_warnings(valid, db) if dry_run and validate_names else []
    return schemas.ImportReport(
        dry_run=dry_run, total=len(payload.rows), created=created,
        updated=updated, skipped=skipped, errors=errors[:200], warnings=warnings,
    )


OK_STATUSES = {"ok"}


# checks GBIF for the distinct names in the file; warnings never block the import
def taxonomy_warnings(valid, db: Session) -> List[schemas.ImportWarning]:
    counts = {}
    for _, item in valid:
        name = item.species.strip()
        counts[name] = counts.get(name, 0) + 1
    if not counts:
        return []
    names = list(counts)[:150]
    results = gbif.validate_names(names, db)
    warnings = []
    unavailable = 0
    for name in names:
        r = results.get(name, {})
        status = r.get("status", "unavailable")
        if status in OK_STATUSES:
            continue
        if status == "unavailable":
            unavailable += counts[name]
            continue
        warnings.append(schemas.ImportWarning(name=name, kind=status, suggestion=r.get("suggestion"), row_count=counts[name]))
    if unavailable:
        warnings.append(schemas.ImportWarning(name="", kind="unavailable", row_count=unavailable))
    return warnings


@app.post("/taxonomy/validate", response_model=List[schemas.ValidatedName])
def validate_scientific_names(
    payload: schemas.ValidateNamesRequest, db: Session = Depends(get_db), auth: None = Depends(require_login)
):
    results = gbif.validate_names(payload.names, db)
    return [schemas.ValidatedName(name=n, **r) for n, r in results.items()]


# --- Export ---
# the column headers are what users see in the downloaded file, so they stay in Portuguese
BASE_COLUMNS = [
    "Codigo Etiqueta", "Ordem", "Familia", "Especie", "Data Coleta", "Local Coleta", "Latitude", "Longitude",
    "Altitude (m)", "Sexo", "Estagio", "Determinador", "Data Determinacao", "Metodo Coleta", "Habitat",
    "Imagem", "Projeto", "Notas",
]
# only present in the full CSV, which requires login
INTERNAL_COLUMNS = [
    "Coletor", "Numero Campo", "Localizacao Fisica", "Emprestimo", "Emprestado Para", "Data Emprestimo", "Notas Internas",
]


@app.get("/export/csv")
def export_specimens_csv(
    project_id: Optional[int] = None, full: bool = False,
    logged_in: bool = Depends(is_logged_in), db: Session = Depends(get_db)
):
    if full and not logged_in:
        raise api_error(401, "full_csv_requires_login")
    query = filter_visible(db.query(models.Specimen), logged_in).options(
        selectinload(models.Specimen.measurements), selectinload(models.Specimen.project)
    )
    if project_id: query = query.filter(models.Specimen.project_id == project_id)
    specimens = query.order_by(models.Specimen.id).all()

    # one column per measured trait, as "Trait (unit)", a format the importer also understands
    traits = []
    for s in specimens:
        for m in s.measurements:
            key = (m.trait, m.unit or "mm")
            if key not in traits:
                traits.append(key)

    output = io.StringIO()
    # BOM so Excel opens the accents correctly
    output.write("﻿")
    writer = csv.writer(output)
    header = BASE_COLUMNS + (INTERNAL_COLUMNS if full else [])
    writer.writerow(header + [f"{t} ({u})" for t, u in traits])
    for s in specimens:
        values = {(m.trait, m.unit or "mm"): m.value for m in s.measurements}
        row = [
            s.catalog_number, s.insect_order, s.family, s.species, s.collection_date, s.locality,
            s.latitude, s.longitude, s.elevation_m, s.sex, s.life_stage, s.identified_by,
            s.identification_date, s.sampling_method, s.habitat, s.image_file,
            s.project.title if s.project else None, s.notes,
        ]
        if full:
            row += [
                s.collector, s.field_number, s.storage_location, s.loan_status,
                s.loaned_to, s.loan_date, s.internal_notes,
            ]
        writer.writerow(row + [values.get(key) for key in traits])
    output.seek(0)
    name = "acervo_entomobase_completo.csv" if full else "acervo_entomobase.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={name}"},
    )


# --- Darwin Core ---
# set these to the collection's values before publishing to GBIF
DWC_INSTITUTION = "UFMG"
DWC_COLLECTION = "EntomoBase"
DWC_LICENSE = "http://creativecommons.org/licenses/by/4.0/legalcode"
DWC_ZENODO_FILE_URL = "https://zenodo.org/records/{record}/files/{file}"

DWC_FIELDS = [
    "occurrenceID", "basisOfRecord", "institutionCode", "collectionCode", "catalogNumber", "datasetName",
    "license", "kingdom", "class", "order", "family", "scientificName", "eventDate", "locality",
    "decimalLatitude", "decimalLongitude", "geodeticDatum", "minimumElevationInMeters", "sex", "lifeStage",
    "identifiedBy", "dateIdentified", "samplingProtocol", "habitat", "associatedMedia", "occurrenceRemarks",
]
DWC_TERMS = "http://rs.tdwg.org/dwc/terms/"


def zenodo_media(s: models.Specimen) -> Optional[str]:
    url = s.project.dataset_url if s.project else None
    if s.photo_url and s.photo_url.startswith("http"):
        return s.photo_url
    if not (url and s.image_file):
        return None
    match = re.search(r"zenodo\.org/records?/(\d+)", url, re.I) or re.search(r"10\.5281/zenodo\.(\d+)", url, re.I)
    # ids starting with 0 belong to the demo data
    if not match or match.group(1).startswith("0"):
        return None
    return DWC_ZENODO_FILE_URL.format(record=match.group(1), file=urllib.parse.quote(s.image_file))


def meta_xml() -> str:
    def fields(names, start):
        return "\n".join(
            f'    <field index="{i}" term="{DWC_TERMS}{name}"/>' for i, name in enumerate(names, start=start)
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<archive xmlns="http://rs.tdwg.org/dwc/text/">\n'
        '  <core encoding="UTF-8" fieldsTerminatedBy="," linesTerminatedBy="\\n" fieldsEnclosedBy="&quot;" ignoreHeaderLines="1" rowType="http://rs.tdwg.org/dwc/terms/Occurrence">\n'
        '    <files><location>occurrence.csv</location></files>\n'
        '    <id index="0"/>\n'
        f'{fields(DWC_FIELDS[1:], 1)}\n'
        '  </core>\n'
        '  <extension encoding="UTF-8" fieldsTerminatedBy="," linesTerminatedBy="\\n" fieldsEnclosedBy="&quot;" ignoreHeaderLines="1" rowType="http://rs.tdwg.org/dwc/terms/MeasurementOrFact">\n'
        '    <files><location>measurementorfact.csv</location></files>\n'
        '    <coreid index="0"/>\n'
        f'{fields(["measurementType", "measurementValue", "measurementUnit"], 1)}\n'
        '  </extension>\n'
        '</archive>\n'
    )


# the Darwin Core export is always public: only finished projects and no internal field
@app.get("/export/dwc")
def export_darwin_core(project_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = filter_visible(db.query(models.Specimen), False).options(
        selectinload(models.Specimen.measurements), selectinload(models.Specimen.project)
    )
    if project_id: query = query.filter(models.Specimen.project_id == project_id)
    specimens = query.order_by(models.Specimen.id).all()

    occurrences = io.StringIO()
    measurements = io.StringIO()
    occurrence_writer = csv.writer(occurrences, lineterminator="\n")
    measurement_writer = csv.writer(measurements, lineterminator="\n")
    occurrence_writer.writerow(DWC_FIELDS)
    measurement_writer.writerow(["occurrenceID", "measurementType", "measurementValue", "measurementUnit"])
    for s in specimens:
        occurrence_id = f"{DWC_INSTITUTION}:{DWC_COLLECTION}:{s.catalog_number}"
        has_coordinates = s.latitude is not None and s.longitude is not None
        occurrence_writer.writerow([
            occurrence_id, "PreservedSpecimen", DWC_INSTITUTION, DWC_COLLECTION, s.catalog_number,
            s.project.title if s.project else "", DWC_LICENSE, "Animalia", "Insecta", s.insect_order,
            s.family, s.species, s.collection_date, s.locality,
            s.latitude, s.longitude, "WGS84" if has_coordinates else "", s.elevation_m, s.sex, s.life_stage,
            s.identified_by, s.identification_date, s.sampling_method, s.habitat, zenodo_media(s), s.notes,
        ])
        for m in s.measurements:
            measurement_writer.writerow([occurrence_id, m.trait, m.value, m.unit])

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("occurrence.csv", occurrences.getvalue())
        archive.writestr("measurementorfact.csv", measurements.getvalue())
        archive.writestr("meta.xml", meta_xml())
    return Response(
        buffer.getvalue(), media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=entomobase_darwincore.zip"},
    )


# --- Demo images (only for the demo data; this route can be removed) ---
@app.get("/demo/image/{file_name}")
def demo_image(file_name: str, db: Session = Depends(get_db)):
    s = db.query(models.Specimen).filter(models.Specimen.image_file == file_name).first()
    if not s:
        raise api_error(404, "image_not_found")
    svg = render_svg(s.insect_order, s.family or "", s.species, s.id, s.catalog_number, s.sex or "")
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})
