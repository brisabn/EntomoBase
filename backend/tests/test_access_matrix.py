# Phase 5 review: every route of the API, for every kind of person, in one table.
# The other files test each rule where it was written; this one makes sure no route was forgotten:
# - the table must list every route the API has (a new route without a line here fails the first test);
# - each route answers each person as its rule says, on both forms of the address (/x and /labs/<slug>/x);
# - no read route lets anything of another laboratory, or anything hidden, reach someone who may not see it;
# - an id of another laboratory gets the very same answer as an id that does not exist.
import io
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest

import mailer
import models
from conftest import SessionLocal, make_token
from email_confirmation import hash_code
from security import hash_password
from laboratories import default_laboratory

FIRST = "ufmg"
OTHER = "lab-b"
NOWHERE = 999_999
# the code of the invitation to the first laboratory, sent to an address with no account
INVITE_CODE = "invite-code-of-a-0123456789"
# every account of the world has this password, hashed once (argon2 is slow on purpose)
WORLD_PASSWORD = "world-password"
WORLD_HASH = hash_password(WORLD_PASSWORD)

# the people who may knock on the door of the first laboratory
PEOPLE = ["visitor", "no_lab", "admin_elsewhere", "superadmin", "researcher", "admin"]


@dataclass
class World:
    ids: dict
    headers: dict


# two laboratories with the same kinds of things, each marked with a word that must not travel
def build_world() -> World:
    db = SessionLocal()
    try:
        first = default_laboratory(db)
        other = models.Laboratory(slug=OTHER, name="Laboratório B", institution="USP", collection_code="LB", license="x", listed=True)
        db.add(other)
        db.flush()

        def project(lab, title, visibility, token=None):
            p = models.Project(laboratory_id=lab.id, title=title, year=2025, insect_group="Coleoptera",
                               visibility=visibility, finished=visibility == "public", share_token=token)
            db.add(p)
            db.flush()
            return p

        def specimen(lab, code, project_id, image=None):
            s = models.Specimen(laboratory_id=lab.id, catalog_number=code, insect_order="Coleoptera", species="Dynastes hercules",
                                project_id=project_id, collector="COLLECTOR-SECRET", storage_location="DRAWER-SECRET",
                                image_file=image, latitude=-19.9, longitude=-43.9)
            db.add(s)
            db.flush()
            return s

        a_public = project(first, "PUBLIC-A", "public")
        a_unlisted = project(first, "UNLISTED-A", "unlisted", "token-of-a-0123456789")
        a_private = project(first, "PRIVATE-A", "private")
        b_public = project(other, "PUBLIC-B-TITLE", "public")
        b_private = project(other, "PRIVATE-B", "private")
        a_spec = specimen(first, "A-PUB-1", a_public.id, image="a-pub-1.jpg")
        specimen(first, "A-UNL-1", a_unlisted.id)
        specimen(first, "A-PRIV-1", a_private.id)
        specimen(first, "A-LOOSE-1", None)
        b_spec = specimen(other, "B-PUB-1", b_public.id, image="b-pub-1.jpg")
        specimen(other, "B-PRIV-1", b_private.id)

        people = {}
        for name, roles, superadmin in [
            ("no_lab", {}, False),
            ("admin_elsewhere", {other.id: "admin"}, False),
            ("superadmin", {}, True),
            ("researcher", {first.id: "researcher"}, False),
            ("admin", {first.id: "admin"}, False),
            ("researcher_b", {other.id: "researcher"}, False),
            # a second admin here, so the admin may leave (the last one cannot; test_members covers that)
            ("second_admin", {first.id: "admin"}, False),
        ]:
            user = models.User(email=f"{name}@lab.br", password_hash=WORLD_HASH, name=name, is_superadmin=superadmin,
                               email_verified_at=datetime(2026, 1, 1))
            db.add(user)
            db.flush()
            for lab_id, role in roles.items():
                db.add(models.Membership(user_id=user.id, laboratory_id=lab_id, role=role))
            people[name] = user
        db.flush()

        def membership(name, lab):
            return db.query(models.Membership).filter_by(user_id=people[name].id, laboratory_id=lab.id).one().id

        def invitation(lab, email, by, code):
            now = datetime.now()
            row = models.Invitation(laboratory_id=lab.id, email=email, role="researcher", invited_by_id=people[by].id,
                                    code_hash=hash_code(code), created_at=now, expires_at=now + timedelta(days=7))
            db.add(row)
            db.flush()
            return row.id

        ids = {
            "a_public": a_public.id, "a_unlisted": a_unlisted.id, "a_private": a_private.id, "a_spec": a_spec.id,
            "b_public": b_public.id, "b_private": b_private.id, "b_spec": b_spec.id,
            "a_member": membership("researcher", first), "b_member": membership("researcher_b", other),
            "a_invitation": invitation(first, "invited_a@lab.br", "admin", INVITE_CODE),
            "b_invitation": invitation(other, "invited_b@lab.br", "admin_elsewhere", "invite-code-of-b-0123456789"),
        }
        db.commit()
        headers = {"visitor": {}}
        headers.update({name: {"Authorization": f"Bearer {make_token(email=f'{name}@lab.br')}"} for name in people})
        return World(ids, headers)
    finally:
        db.close()


@pytest.fixture
def world():
    return build_world()


# inviting sends an e-mail; here it stays in memory
@pytest.fixture(autouse=True)
def mail_in_memory(monkeypatch):
    monkeypatch.setenv("MAIL_BACKEND", "memory")
    monkeypatch.setenv("SITE_URL", "https://entomobase.example")
    mailer.outbox.clear()


# ---------- the table ----------
# who gets in, by rule; everyone else is refused with the status shown
RULES = {
    # anyone, logged in or not
    "public": {p: "ok" for p in PEOPLE},
    # any account
    "account": {**{p: "ok" for p in PEOPLE}, "visitor": 401},
    # a researcher or an admin of the laboratory of the address
    "member": {"visitor": 401, "no_lab": 403, "admin_elsewhere": 403, "superadmin": 403, "researcher": "ok", "admin": "ok"},
    # an admin of the laboratory of the address
    "admin": {"visitor": 401, "no_lab": 403, "admin_elsewhere": 403, "superadmin": 403, "researcher": 403, "admin": "ok"},
    # the administrator of the platform
    "superadmin": {"visitor": 401, "no_lab": 403, "admin_elsewhere": 403, "superadmin": "ok", "researcher": 403, "admin": 403},
}


# one line per way of using a route: (method, path after the laboratory, rule, success status, request)
# the request gets the ids of the world and returns (address after the laboratory, json body)
@dataclass
class Case:
    method: str
    path: str
    rule: str
    success: int
    request: object
    in_lab: bool = True  # False: a route of the platform, which has no laboratory in its address


CASES = [
    # the laboratory
    Case("GET", "/laboratory", "public", 200, lambda i: ("/laboratory", None)),
    # projects
    Case("GET", "/projects", "public", 200, lambda i: ("/projects", None)),
    Case("POST", "/projects", "member", 201, lambda i: ("/projects", {"title": "New", "year": 2026, "insect_group": "Diptera"})),
    Case("PUT", "/projects/{project_id}", "member", 200, lambda i: (f"/projects/{i['a_private']}", {"title": "Renamed"})),
    Case("DELETE", "/projects/{project_id}", "admin", 204, lambda i: (f"/projects/{i['a_private']}", None)),
    # specimens
    Case("GET", "/specimens", "public", 200, lambda i: ("/specimens", None)),
    Case("POST", "/specimens", "member", 201, lambda i: ("/specimens", {"catalog_number": "NEW-1", "insect_order": "Diptera", "species": "Musca domestica", "project_id": i["a_private"]})),
    Case("PUT", "/specimens/{specimen_id}", "member", 200, lambda i: (f"/specimens/{i['a_spec']}", {"locality": "Changed"})),
    Case("DELETE", "/specimens/{specimen_id}", "member", 204, lambda i: (f"/specimens/{i['a_spec']}", None)),
    Case("POST", "/specimens/import", "member", 200, lambda i: ("/specimens/import", {"project_id": i["a_private"], "rows": [{"catalog_number": "IMP-1", "insect_order": "Diptera", "species": "Musca domestica"}]})),
    Case("POST", "/taxonomy/validate", "member", 200, lambda i: ("/taxonomy/validate", {"names": ["Musca domestica"]})),
    # exports: the normal file is public data for anyone; the full one, with internal columns, is for members
    Case("GET", "/export/csv", "public", 200, lambda i: ("/export/csv", None)),
    Case("GET", "/export/csv", "member", 200, lambda i: ("/export/csv?full=true", None)),
    Case("GET", "/export/dwc", "public", 200, lambda i: ("/export/dwc", None)),
    Case("GET", "/demo/image/{file_name}", "public", 200, lambda i: ("/demo/image/a-pub-1.jpg", None)),
    # members (only with the laboratory in the address)
    Case("GET", "/members", "admin", 200, lambda i: ("/members", None)),
    Case("PUT", "/members/{member_id}", "admin", 200, lambda i: (f"/members/{i['a_member']}", {"role": "admin"})),
    Case("DELETE", "/members/{member_id}", "admin", 204, lambda i: (f"/members/{i['a_member']}", None)),
    Case("DELETE", "/membership", "member", 204, lambda i: ("/membership", None)),
    Case("GET", "/invitations", "admin", 200, lambda i: ("/invitations", None)),
    Case("POST", "/invitations", "admin", 201, lambda i: ("/invitations", {"email": "someone.new@lab.br", "role": "researcher"})),
    Case("DELETE", "/invitations/{invitation_id}", "admin", 204, lambda i: (f"/invitations/{i['a_invitation']}", None)),
    # the platform
    Case("GET", "/labs", "public", 200, lambda i: ("/labs", None), in_lab=False),
    Case("GET", "/overview", "public", 200, lambda i: ("/overview", None), in_lab=False),
    Case("GET", "/map", "public", 200, lambda i: ("/map", None), in_lab=False),
    Case("GET", "/me", "account", 200, lambda i: ("/me", None), in_lab=False),
    Case("PUT", "/me/password", "account", 200,
         lambda i: ("/me/password", {"current_password": WORLD_PASSWORD, "new_password": "a-new-password"}), in_lab=False),
    Case("POST", "/labs", "superadmin", 201, lambda i: ("/labs", {"slug": "lab-new", "name": "N", "institution": "I", "collection_code": "N", "admin_email": "no_lab@lab.br"}), in_lab=False),
    Case("GET", "/shared/{token}", "public", 200, lambda i: ("/shared/token-of-a-0123456789", None), in_lab=False),
    Case("GET", "/shared/{token}/specimens", "public", 200, lambda i: ("/shared/token-of-a-0123456789/specimens", None), in_lab=False),
    # the link of an invitation: whoever has the code (it went to that mailbox). This one is for an address with
    # no account, so anyone holding it creates the account; with an account, test_invitations asks for a login
    Case("GET", "/invitations/{code}", "public", 200, lambda i: (f"/invitations/{INVITE_CODE}", None), in_lab=False),
    Case("POST", "/invitations/{code}/accept", "public", 200,
         lambda i: (f"/invitations/{INVITE_CODE}/accept", {"name": "Invited", "password": "a-good-password"}), in_lab=False),
]

# the routes anyone may call without an account by design; their own rules (wrong password, rate limits,
# confirmation codes) are tested in test_auth, test_signup, test_confirm and test_passwords
OPEN_BY_DESIGN = {("POST", "/login"), ("POST", "/signup"), ("POST", "/confirm"), ("POST", "/forgot-password"), ("POST", "/reset-password")}

# the old addresses without a laboratory mean the first one; the members routes never had them
MEMBERS_ONLY_WITH_SLUG = {"/members", "/members/{member_id}", "/membership", "/invitations", "/invitations/{invitation_id}"}


def addresses(case):
    if not case.in_lab:
        return [("platform", "")]
    forms = [("slug", f"/labs/{FIRST}")]
    if case.path not in MEMBERS_ONLY_WITH_SLUG:
        forms.insert(0, ("old", ""))
    return forms


def call(client, method, url, headers, body=None):
    return client.request(method, url, headers=headers, json=body)


# what a person can read in an answer: the Darwin Core is a zip, so its files are read one by one
# (searching the compressed bytes would find nothing and prove nothing)
def readable(response):
    if response.content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            return "\n".join(f"{name}:\n" + archive.read(name).decode("utf-8") for name in sorted(archive.namelist()))
    return response.text


# ---------- 1. the table lists every route ----------
def test_every_route_of_the_api_is_in_the_table(app):
    routes = {(m.upper(), path) for path, ops in app.openapi()["paths"].items() for m in ops}
    listed = set(OPEN_BY_DESIGN)
    for case in CASES:
        for form, prefix in addresses(case):
            listed.add((case.method, ("/labs/{slug}" if form == "slug" else "") + case.path))
    assert routes - listed == set(), "routes without a line in the access table"
    assert listed - routes == set(), "lines in the access table for routes that no longer exist"


# ---------- 2. each person gets what the rule says, on every form of the address ----------
MATRIX = [(case, form, prefix, person) for case in CASES for form, prefix in addresses(case) for person in PEOPLE]


def case_id(case, form, person):
    url, _ = case.request({k: 1 for k in ("a_public", "a_unlisted", "a_private", "a_spec", "a_member", "a_invitation")})
    return f"{case.method} {url.replace('1', '<id>') if '{' in case.path else url} [{form}] {person}"


@pytest.mark.parametrize("case,form,prefix,person", MATRIX, ids=[case_id(c, f, p) for c, f, _, p in MATRIX])
def test_each_person_gets_what_the_rule_of_the_route_says(client, world, case, form, prefix, person):
    path, body = case.request(world.ids)
    response = call(client, case.method, prefix + path, world.headers[person], body)
    expected = RULES[case.rule][person]
    assert response.status_code == (case.success if expected == "ok" else expected), response.text


def test_the_routes_open_by_design_never_ask_for_an_account(client):
    for method, path in OPEN_BY_DESIGN:
        response = call(client, method, path, {}, {})
        # a missing body is a validation error, never a demand for a token or a refusal by role
        assert response.status_code == 422, (path, response.text)


# ---------- 3. nothing hidden or from another laboratory reaches whoever may not see it ----------
READS = [c for c in CASES if c.method == "GET"]
SECRETS_OF_A = ["UNLISTED-A", "PRIVATE-A", "A-UNL-1", "A-PRIV-1", "A-LOOSE-1", "COLLECTOR-SECRET", "DRAWER-SECRET"]
# the e-mails of the people of the other laboratory too: a list of members must never show them here
EVERYTHING_OF_B = ["PUBLIC-B-TITLE", "PRIVATE-B", "B-PUB-1", "B-PRIV-1", "researcher_b@", "admin_elsewhere@", "invited_b@"]
# the platform routes show the public data of every listed laboratory; only hidden things must stay out
SECRETS_OF_B = ["PRIVATE-B", "B-PRIV-1"]


def everything_read_by(client, world, person):
    texts = {}
    for case in READS:
        for form, prefix in addresses(case):
            path, _ = case.request(world.ids)
            response = call(client, "GET", prefix + path, world.headers[person])
            texts[(case.path, path, form)] = (case, readable(response) if response.status_code == 200 else "")
    return texts


@pytest.mark.parametrize("person", PEOPLE)
def test_no_read_route_lets_out_what_the_person_may_not_see(client, world, person):
    member = RULES["member"][person] == "ok"
    for key, (case, text) in everything_read_by(client, world, person).items():
        shared = case.path.startswith("/shared")
        hidden_of_a = [] if member or shared else SECRETS_OF_A
        if shared:
            # the link shows its own project, never the internal fields nor other projects
            hidden_of_a = ["PRIVATE-A", "A-PRIV-1", "A-LOOSE-1", "COLLECTOR-SECRET", "DRAWER-SECRET"]
        of_b = SECRETS_OF_B if not case.in_lab else EVERYTHING_OF_B
        leaked = [word for word in hidden_of_a + of_b if word in text]
        assert leaked == [], f"{key}: {leaked}"


@pytest.mark.parametrize("person", PEOPLE)
def test_the_reads_do_return_data_so_the_check_above_means_something(client, world, person):
    texts = everything_read_by(client, world, person)
    for path in ("/projects", "/specimens", "/export/csv", "/export/dwc"):
        found = [text for (route, url, _), (_, text) in texts.items() if route == path and "full=" not in url]
        assert found and all(("A-PUB-1" in t or "PUBLIC-A" in t) for t in found), path
    if RULES["member"][person] == "ok":
        assert "A-PRIV-1" in texts[("/specimens", "/specimens", "old")][1]
        assert "COLLECTOR-SECRET" in texts[("/export/csv", "/export/csv?full=true", "old")][1]


# ---------- 4. an id of another laboratory is the same as an id that does not exist ----------
# (route, the address with an id of the other laboratory, the same with an id that does not exist, body)
def with_ids(i, project, specimen, member, invitation):
    return [
        ("PUT", f"/projects/{project}", {"title": "Hijacked"}),
        ("DELETE", f"/projects/{project}", None),
        ("PUT", f"/specimens/{specimen}", {"locality": "Hijacked"}),
        ("DELETE", f"/specimens/{specimen}", None),
        ("POST", "/specimens", {"catalog_number": "X-1", "insect_order": "Diptera", "species": "Musca domestica", "project_id": project}),
        ("PUT", f"/specimens/{i['a_spec']}", {"project_id": project}),
        ("POST", "/specimens/import", {"project_id": project, "rows": [{"catalog_number": "X-2", "insect_order": "Diptera", "species": "Musca domestica"}]}),
        ("GET", f"/export/csv?project_id={project}", None),
        ("GET", f"/export/csv?full=true&project_id={project}", None),
        ("GET", f"/export/dwc?project_id={project}", None),
        ("PUT", f"/members/{member}", {"role": "admin"}),
        ("DELETE", f"/members/{member}", None),
        ("DELETE", f"/invitations/{invitation}", None),
    ]


def snapshot(db):
    db.expire_all()
    return (
        sorted((p.id, p.title, p.visibility, p.laboratory_id) for p in db.query(models.Project).all()),
        sorted((s.id, s.catalog_number, s.locality, s.project_id, s.laboratory_id) for s in db.query(models.Specimen).all()),
        sorted((m.id, m.role) for m in db.query(models.Membership).all()),
        sorted((v.id, v.email, v.role, v.laboratory_id) for v in db.query(models.Invitation).all()),
    )


@pytest.mark.parametrize("person", ["admin", "researcher"])
@pytest.mark.parametrize("target", ["b_public", "b_private"])
def test_an_id_of_another_laboratory_gets_the_same_answer_as_one_that_does_not_exist(client, world, db, person, target):
    i = world.ids
    foreign = with_ids(i, i[target], i["b_spec"], i["b_member"], i["b_invitation"])
    missing = with_ids(i, NOWHERE, NOWHERE, NOWHERE, NOWHERE)
    for (method, path, body), (_, nowhere_path, nowhere_body) in zip(foreign, missing):
        prefix = f"/labs/{FIRST}"
        if person == "researcher" and path.startswith(("/members", "/invitations")):
            continue  # a researcher never reaches the members routes (see the table)
        before = snapshot(db)
        a = call(client, method, prefix + path, world.headers[person], body)
        b = call(client, method, prefix + nowhere_path, world.headers[person], nowhere_body)
        assert (a.status_code, readable(a)) == (b.status_code, readable(b)), f"{method} {path}"
        assert snapshot(db) == before, f"{method} {path} changed something"


# the same, from the other side: whoever manages the other laboratory reaches nothing here through it
def test_the_admin_of_another_laboratory_reaches_nothing_here_through_their_own(client, world, db):
    i = world.ids
    before = snapshot(db)
    for method, path, body in with_ids(i, i["a_private"], i["a_spec"], i["a_member"], i["a_invitation"]):
        if path.startswith(f"/specimens/{i['a_spec']}") and body == {"project_id": i["a_private"]}:
            continue  # this line moves a specimen of the first laboratory, which is already covered above
        response = call(client, method, f"/labs/{OTHER}" + path, world.headers["admin_elsewhere"], body)
        assert response.status_code in (200, 400, 404), f"{method} {path}: {response.status_code}"
        for word in SECRETS_OF_A + ["PUBLIC-A", "A-PUB-1"]:
            assert word not in readable(response), f"{method} {path} let out {word}"
    after = snapshot(db)
    assert (after[0], after[2], after[3]) == (before[0], before[2], before[3])
    # the specimens of the first laboratory are untouched; the import may have created one in the other
    first_lab_specimens = [s for s in snapshot(db)[1] if s[4] == default_laboratory(db).id]
    assert first_lab_specimens == [s for s in before[1] if s[4] == default_laboratory(db).id]
