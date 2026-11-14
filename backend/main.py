import csv
import io
import os
import re
import urllib.parse
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import jwt
from fastapi.responses import JSONResponse, StreamingResponse, Response
from fastapi import APIRouter, FastAPI, Depends, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional

import gbif
import models
import platform_map
import public_numbers
import schemas
from database import get_db
from db_setup import initialize_database
from authorization import (
    Context, get_context, get_visible_project, get_visible_specimen, public_specimens, require_admin,
    require_member, require_superadmin, required_user, set_visibility, unauthenticated, user_from_token,
    visible_projects, visible_specimens,
)
from errors import api_error
from invitations import issue_invitation, send_invitation, usable_invitation
from laboratories import DEFAULT_LABORATORY
from demo_images import render_svg
from email_confirmation import (
    RESET_VALID_HOURS, hash_code, issue_code, send_already_registered, send_confirmation, send_no_account,
    send_password_reset, utc_now,
)
from mailer import MailError, valid_address
from rate_limit import AttemptLimiter
from security import MIN_PASSWORD_LENGTH, hash_password, needs_rehash, verify_password
from settings import ALGORITHM, SECRET_KEY

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

# the routes that work on one laboratory's data; login and share links do not belong to a laboratory
lab_router = APIRouter()
# routes that exist only with the laboratory in the address, with no old address without it
members_router = APIRouter()


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
    # an unconfirmed account may still be taken over by whoever owns the address (see /signup), so it gets
    # no session; the person signs up again to receive a new link
    if user.email_verified_at is None:
        raise api_error(403, "email_not_confirmed")
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(credentials.password)
        db.commit()
    return {"access_token": new_session_token(user), "email": user.email}


SESSION_HOURS = 8


def new_session_token(user: models.User) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)
    return jwt.encode({"sub": user.email, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)


# open sign-up, which sends an e-mail to whatever address is typed, so it is limited per IP: every request
# counts, not only the failed ones
SIGNUP_WINDOW_SECONDS = 60 * 60
signup_limiter = AttemptLimiter(max_attempts=5, window_seconds=SIGNUP_WINDOW_SECONDS)


# creates an account with no laboratory and e-mails a link to confirm the address. The answer is the same
# whether or not the address already has an account, so the route cannot be used to find out who is registered
@app.post("/signup", status_code=202)
def signup(data: schemas.SignupRequest, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    ensure_login_allowed((signup_limiter, ip))
    signup_limiter.record_failure(ip)

    email = data.email.lower()
    if not valid_address(email):
        raise api_error(400, "invalid_email")
    if len(data.password) < MIN_PASSWORD_LENGTH:
        raise api_error(400, "weak_password", minimum=MIN_PASSWORD_LENGTH)

    # hashed before looking at the database, so the time taken does not show whether the address exists
    password_hash = hash_password(data.password)
    user = db.query(models.User).filter(func.lower(models.User.email) == email).first()
    try:
        if user is not None and user.email_verified_at is not None:
            send_already_registered(email)
        else:
            # an account whose address was never confirmed is taken over by the newest sign-up: whoever
            # types an address first does not keep it from the person who owns it
            if user is None:
                user = models.User(email=email, password_hash=password_hash, name=data.name)
                db.add(user)
            else:
                user.password_hash, user.name = password_hash, data.name
            db.flush()
            send_confirmation(email, issue_code(db, user))
        db.commit()
    except MailError:
        db.rollback()
        raise api_error(503, "mail_unavailable")
    except IntegrityError:
        # two sign-ups for the same new address at the same moment: the other one wins and sends the e-mail
        db.rollback()
    return {"status": "confirmation_sent"}


# the link in the e-mail opens the site, which sends the code here. A code works once and only until it
# expires; it is long and random, so guessing one is not a concern. No session is given: the person signs in
@app.post("/confirm")
def confirm_email(data: schemas.ConfirmRequest, db: Session = Depends(get_db)):
    confirmation = db.query(models.EmailConfirmation).filter(models.EmailConfirmation.code_hash == hash_code(data.code)).first()
    if confirmation is None or confirmation.expires_at <= utc_now():
        raise api_error(400, "invalid_code")
    user = confirmation.user
    if user.email_verified_at is None:
        user.email_verified_at = utc_now()
    db.query(models.EmailConfirmation).filter(models.EmailConfirmation.user_id == user.id).delete()
    db.commit()
    return {"status": "confirmed", "email": user.email}


# --- Passwords ---
# asking for a new password sends an e-mail to whatever address is typed, so every request counts, per IP and
# per address (nobody fills someone else's mailbox with links)
RESET_WINDOW_SECONDS = 60 * 60
reset_ip_limiter = AttemptLimiter(max_attempts=5, window_seconds=RESET_WINDOW_SECONDS)
reset_email_limiter = AttemptLimiter(max_attempts=3, window_seconds=RESET_WINDOW_SECONDS)


# the answer is the same whether or not the address has an account, and so is what happens: an e-mail goes out
# either way (with the link, or saying there is no account), so not even a failing mail server tells them apart
@app.post("/forgot-password", status_code=202)
def forgot_password(data: schemas.ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    email = data.email.lower()
    if not valid_address(email):
        raise api_error(400, "invalid_email")
    ensure_login_allowed((reset_ip_limiter, ip), (reset_email_limiter, email))
    reset_ip_limiter.record_failure(ip)
    reset_email_limiter.record_failure(email)
    user = user_with_email(db, email)
    try:
        if user is None:
            send_no_account(email)
        else:
            send_password_reset(email, issue_code(db, user, hours=RESET_VALID_HOURS))
        db.commit()
    except MailError:
        db.rollback()
        raise api_error(503, "mail_unavailable")
    return {"status": "reset_sent"}


# the link of that e-mail opens the site, which sends the code with the new password. Choosing it also confirms
# the address (the link reached that mailbox), and every other link of the account stops working
@app.post("/reset-password")
def reset_password(data: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    confirmation = db.query(models.EmailConfirmation).filter(models.EmailConfirmation.code_hash == hash_code(data.code)).first()
    if confirmation is None or confirmation.expires_at <= utc_now():
        raise api_error(400, "invalid_reset_code")
    if len(data.password) < MIN_PASSWORD_LENGTH:
        raise api_error(400, "weak_password", minimum=MIN_PASSWORD_LENGTH)
    user = confirmation.user
    user.password_hash = hash_password(data.password)
    if user.email_verified_at is None:
        user.email_verified_at = utc_now()
    db.query(models.EmailConfirmation).filter(models.EmailConfirmation.user_id == user.id).delete()
    db.commit()
    return {"status": "password_changed", "email": user.email}


# a signed-in person changes their own password, giving the current one. A wrong one counts like a wrong
# password at the login (the session could be on a borrowed computer), and is a 400, not a 401: the site
# signs the person out on a 401
@app.put("/me/password")
def change_password(data: schemas.PasswordChange, request: Request, user: models.User = Depends(required_user),
                    db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    account_key = (ip, user.email.lower())
    ensure_login_allowed((account_limiter, account_key), (ip_limiter, ip))
    if not verify_password(data.current_password, user.password_hash):
        account_limiter.record_failure(account_key)
        ip_limiter.record_failure(ip)
        raise api_error(400, "wrong_password")
    account_limiter.reset(account_key)
    if len(data.new_password) < MIN_PASSWORD_LENGTH:
        raise api_error(400, "weak_password", minimum=MIN_PASSWORD_LENGTH)
    user.password_hash = hash_password(data.new_password)
    # a link to choose a password, sent before, must not undo this one
    db.query(models.EmailConfirmation).filter(models.EmailConfirmation.user_id == user.id).delete()
    db.commit()
    return {"status": "password_changed"}


# who is signed in and where they work; the role in each laboratory is read now, not taken from the token
@app.get("/me", response_model=schemas.Me)
def me(user: models.User = Depends(required_user), db: Session = Depends(get_db)):
    rows = db.query(models.Membership, models.Laboratory).join(models.Laboratory, models.Membership.laboratory_id == models.Laboratory.id).filter(
        models.Membership.user_id == user.id
    ).order_by(models.Laboratory.name, models.Laboratory.id).all()
    laboratories = [schemas.MyLaboratory(slug=lab.slug, name=lab.name, role=m.role) for m, lab in rows]
    return schemas.Me(email=user.email, name=user.name, is_superadmin=user.is_superadmin, laboratories=laboratories)


def user_with_email(db: Session, email: str) -> Optional[models.User]:
    return db.query(models.User).filter(func.lower(models.User.email) == email.strip().lower()).first()


# the account with this e-mail, if its address was confirmed: an unconfirmed one may still change hands
# (see /signup), so it never counts as an account
def confirmed_account(db: Session, email: str) -> Optional[models.User]:
    user = user_with_email(db, email)
    return user if user is not None and user.email_verified_at is not None else None


# the same, for a route that needs one; an unconfirmed account is reported as missing, like one that is
def confirmed_user(db: Session, email: str) -> models.User:
    user = confirmed_account(db, email)
    if user is None:
        raise api_error(404, "user_not_found")
    return user


# --- Invitations: the link in the e-mail ---
def invitation_or_404(db: Session, code: str) -> models.Invitation:
    invitation = usable_invitation(db, code)
    if invitation is None:
        raise api_error(404, "invitation_not_found")
    return invitation


# what the page of the link shows. Whoever has the code got it in that mailbox, so telling them whether the
# address has an account reveals nothing they could not find out by signing up
@app.get("/invitations/{code}", response_model=schemas.InvitationPublic)
def show_invitation(code: str, db: Session = Depends(get_db)):
    invitation = invitation_or_404(db, code)
    return schemas.InvitationPublic(
        laboratory=schemas.InvitationLaboratory(slug=invitation.laboratory.slug, name=invitation.laboratory.name),
        email=invitation.email, role=invitation.role, has_account=confirmed_account(db, invitation.email) is not None,
    )


# someone with an account accepts while signed in as that account: the link alone does not put an account
# into a laboratory. Someone without one creates it here, already confirmed (the link reached their mailbox),
# and is signed in at once. An account whose address was never confirmed is taken over, like in /signup
@app.post("/invitations/{code}/accept")
def accept_invitation(code: str, data: Optional[schemas.InvitationAccept] = None, authorization: str = Header(None),
                      db: Session = Depends(get_db)):
    invitation = invitation_or_404(db, code)
    user = user_with_email(db, invitation.email)
    creates_account = user is None or user.email_verified_at is None
    token = None
    if not creates_account:
        current = user_from_token(authorization, db)
        if current is None:
            raise unauthenticated(authorization)
        if current.id != user.id:
            raise api_error(403, "wrong_account")
    else:
        name, password = (data.name, data.password) if data else (None, None)
        if not name:
            raise api_error(400, "name_required")
        if len(password or "") < MIN_PASSWORD_LENGTH:
            raise api_error(400, "weak_password", minimum=MIN_PASSWORD_LENGTH)
        password_hash = hash_password(password)

    laboratory = invitation.laboratory
    try:
        if creates_account:
            if user is None:
                user = models.User(email=invitation.email)
                db.add(user)
            user.password_hash, user.name, user.email_verified_at = password_hash, name, utc_now()
            db.flush()
            # a confirmation link sent before, for the account being taken over, must not work any more
            db.query(models.EmailConfirmation).filter(models.EmailConfirmation.user_id == user.id).delete()
            token = new_session_token(user)
        membership = db.query(models.Membership).filter_by(user_id=user.id, laboratory_id=invitation.laboratory_id).first()
        if membership is None:
            membership = models.Membership(user_id=user.id, laboratory_id=invitation.laboratory_id, role=invitation.role)
            db.add(membership)
        db.delete(invitation)
        db.commit()
    except IntegrityError:
        # the same link used twice at the same moment, both creating the account: the other request won
        db.rollback()
        raise api_error(404, "invitation_not_found")
    return {
        "laboratory": {"slug": laboratory.slug, "name": laboratory.name}, "role": membership.role,
        "email": user.email, "access_token": token,
    }


# --- Laboratories ---
# the public list of the platform: only the laboratories that chose to be listed. A laboratory that is not
# listed still works at its own address; it just is not advertised
@app.get("/labs", response_model=List[schemas.LaboratorySummary])
def list_laboratories(db: Session = Depends(get_db)):
    labs = db.query(models.Laboratory).filter(models.Laboratory.listed == True).order_by(models.Laboratory.name, models.Laboratory.id).all()
    numbers = public_numbers.numbers_by_laboratory(db, [lab.id for lab in labs])
    return [
        schemas.LaboratorySummary(
            **schemas.LaboratoryPublic.model_validate(lab).model_dump(), **numbers[lab.id],
            cover=public_numbers.laboratory_cover(db, lab.id),
        )
        for lab in labs
    ]


@app.get("/overview", response_model=schemas.PlatformTotals)
def platform_overview(db: Session = Depends(get_db)):
    return public_numbers.platform_totals(db)


@app.get("/map", response_model=List[schemas.MapPoint])
def platform_map_points(db: Session = Depends(get_db)):
    return platform_map.map_points(db)


# what anyone may know about the laboratory of the address, listed or not: whoever has the address can
# already see its public data. Without a laboratory in the address it is the first one, like the other old routes
@lab_router.get("/laboratory", response_model=schemas.LaboratoryPublic)
def laboratory_info(ctx: Context = Depends(get_context)):
    return ctx.laboratory


# every laboratory, also the ones out of the public list, for the platform administrator: to see what exists,
# which addresses are taken and who manages each one. No projects or specimens: those stay with the members
@app.get("/platform/laboratories", response_model=List[schemas.PlatformLaboratory])
def platform_laboratories(db: Session = Depends(get_db), superadmin: models.User = Depends(require_superadmin)):
    labs = db.query(models.Laboratory).order_by(models.Laboratory.name, models.Laboratory.id).all()
    rows = db.query(models.Membership.laboratory_id, models.Membership.role, models.User.email).join(
        models.User, models.Membership.user_id == models.User.id
    ).order_by(models.User.email).all()
    members, admins = {}, {}
    for lab_id, role, email in rows:
        members[lab_id] = members.get(lab_id, 0) + 1
        if role == "admin":
            admins.setdefault(lab_id, []).append(email)
    return [
        schemas.PlatformLaboratory(
            slug=lab.slug, name=lab.name, institution=lab.institution, collection_code=lab.collection_code,
            license=lab.license, listed=lab.listed, members=members.get(lab.id, 0), admins=admins.get(lab.id, []),
        )
        for lab in labs
    ]


# only a platform administrator creates laboratories. The new one starts with a single member, the admin named
# in the request; the platform administrator has no access to the laboratory's data unless also a member
@app.post("/labs", response_model=schemas.LaboratoryPublic, status_code=201)
def create_laboratory(data: schemas.LaboratoryCreate, db: Session = Depends(get_db), superadmin: models.User = Depends(require_superadmin)):
    admin = confirmed_user(db, data.admin_email)
    if db.query(models.Laboratory).filter(models.Laboratory.slug == data.slug).first():
        raise api_error(400, "duplicate_slug")
    laboratory = models.Laboratory(
        slug=data.slug, name=data.name.strip(), institution=data.institution.strip(), collection_code=data.collection_code.strip(),
        license=data.license or DEFAULT_LABORATORY["license"], listed=data.listed,
    )
    laboratory.memberships.append(models.Membership(user_id=admin.id, role="admin"))
    db.add(laboratory)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise api_error(400, "duplicate_slug")
    db.refresh(laboratory)
    return laboratory


# --- Members ---
# only the admins of a laboratory see who belongs to it
@members_router.get("/members", response_model=List[schemas.MemberResponse])
def list_members(db: Session = Depends(get_db), ctx: Context = Depends(require_admin)):
    rows = db.query(models.Membership, models.User).join(models.User, models.Membership.user_id == models.User.id).filter(
        models.Membership.laboratory_id == ctx.laboratory.id
    ).order_by(models.User.email).all()
    return [schemas.MemberResponse(id=m.id, email=u.email, name=u.name, role=m.role) for m, u in rows]


# nobody is put into a laboratory directly: an admin invites them (below) and they accept


# the membership with this id, if it belongs to the laboratory of the request; any other id is a 404
def get_membership(db: Session, ctx: Context, member_id: int) -> models.Membership:
    membership = db.query(models.Membership).filter(
        models.Membership.id == member_id, models.Membership.laboratory_id == ctx.laboratory.id
    ).first()
    if membership is None:
        raise api_error(404, "member_not_found")
    return membership


# a laboratory always keeps at least one admin, or nobody could manage it any more
def other_admins(db: Session, membership: models.Membership) -> int:
    return db.query(models.Membership).filter(
        models.Membership.laboratory_id == membership.laboratory_id, models.Membership.role == "admin",
        models.Membership.id != membership.id,
    ).count()


@members_router.put("/members/{member_id}", response_model=schemas.MemberResponse)
def change_member_role(member_id: int, data: schemas.MemberUpdate, db: Session = Depends(get_db), ctx: Context = Depends(require_admin)):
    membership = get_membership(db, ctx, member_id)
    if membership.role == "admin" and data.role != "admin" and other_admins(db, membership) == 0:
        raise api_error(400, "last_admin")
    membership.role = data.role
    db.commit()
    return schemas.MemberResponse(id=membership.id, email=membership.user.email, name=membership.user.name, role=membership.role)


# removing someone only ends their access to this laboratory; the account and any other membership stay
@members_router.delete("/members/{member_id}", status_code=204)
def remove_member(member_id: int, db: Session = Depends(get_db), ctx: Context = Depends(require_admin)):
    membership = get_membership(db, ctx, member_id)
    if membership.role == "admin" and other_admins(db, membership) == 0:
        raise api_error(400, "last_admin")
    db.delete(membership)
    db.commit()
    return None


# any member leaves on their own. The address has no id, so it can only ever be the person's own membership,
# in the laboratory of the address. The last admin cannot leave, or nobody could manage the laboratory; the
# invitations a leaving admin sent stop working too (see usable_invitation)
@members_router.delete("/membership", status_code=204)
def leave_laboratory(db: Session = Depends(get_db), ctx: Context = Depends(require_member)):
    membership = db.query(models.Membership).filter_by(user_id=ctx.user.id, laboratory_id=ctx.laboratory.id).one()
    if membership.role == "admin" and other_admins(db, membership) == 0:
        raise api_error(400, "last_admin")
    db.delete(membership)
    db.commit()
    return None


# --- Invitations: what the admins do ---
# every e-mail sent counts, so an admin account cannot be used to send e-mail to anyone in bulk
INVITATION_WINDOW_SECONDS = 60 * 60
invitation_limiter = AttemptLimiter(max_attempts=20, window_seconds=INVITATION_WINDOW_SECONDS)


@members_router.get("/invitations", response_model=List[schemas.InvitationResponse])
def list_invitations(db: Session = Depends(get_db), ctx: Context = Depends(require_admin)):
    return db.query(models.Invitation).filter(models.Invitation.laboratory_id == ctx.laboratory.id).order_by(models.Invitation.email).all()


# invites anyone by e-mail, whether or not the address has an account, and the answer is the same either way:
# a list of who is registered must not be one invitation away. The only refusal is for someone already in
# this laboratory, whom the admin already sees in the list of members. Inviting again sends a new link and
# ends the old one
@members_router.post("/invitations", response_model=schemas.InvitationResponse, status_code=201)
def invite(data: schemas.InvitationCreate, db: Session = Depends(get_db), ctx: Context = Depends(require_admin)):
    email = data.email.lower()
    if not valid_address(email):
        raise api_error(400, "invalid_email")
    user = user_with_email(db, email)
    if user is not None and db.query(models.Membership).filter_by(user_id=user.id, laboratory_id=ctx.laboratory.id).first():
        raise api_error(400, "already_member")
    ensure_login_allowed((invitation_limiter, ctx.user.id))
    try:
        invitation, code = issue_invitation(db, ctx.laboratory, email, data.role, ctx.user)
    except IntegrityError:
        # another invitation for the same address was created at the same moment: this one replaces it
        db.rollback()
        invitation, code = issue_invitation(db, ctx.laboratory, email, data.role, ctx.user)
    try:
        send_invitation(invitation, code)
    except MailError:
        db.rollback()
        raise api_error(503, "mail_unavailable")
    invitation_limiter.record_failure(ctx.user.id)
    db.commit()
    db.refresh(invitation)
    return invitation


@members_router.delete("/invitations/{invitation_id}", status_code=204)
def cancel_invitation(invitation_id: int, db: Session = Depends(get_db), ctx: Context = Depends(require_admin)):
    invitation = db.query(models.Invitation).filter(
        models.Invitation.id == invitation_id, models.Invitation.laboratory_id == ctx.laboratory.id
    ).first()
    if invitation is None:
        raise api_error(404, "invitation_not_found")
    db.delete(invitation)
    db.commit()
    return None


# --- Project routes ---
# who can do what is decided in authorization.py; these routes only declare the minimum role they need
# and read data through visible_projects / visible_specimens, never straight from the tables
def project_output(project: models.Project, ctx: Context) -> schemas.ProjectResponse:
    output = schemas.ProjectResponse.model_validate(project)
    # the share link is for the laboratory; to everyone else the project is just public
    if not ctx.is_member:
        output.share_token = None
    return output


@lab_router.post("/projects", response_model=schemas.ProjectResponse, status_code=201)
def create_project(project: schemas.ProjectCreate, db: Session = Depends(get_db), ctx: Context = Depends(require_member)):
    db_project = models.Project(**project.model_dump(exclude={"visibility"}), laboratory_id=ctx.laboratory.id)
    set_visibility(db_project, project.visibility)
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


@lab_router.get("/projects", response_model=List[schemas.ProjectResponse])
def list_projects(
    year: Optional[int] = None, insect_group: Optional[str] = None,
    locality: Optional[str] = None, finished: Optional[bool] = None,
    visibility: Optional[schemas.Visibility] = None,
    ctx: Context = Depends(get_context), db: Session = Depends(get_db)
):
    query = visible_projects(db, ctx)
    if finished is not None: query = query.filter(models.Project.finished == finished)
    if visibility: query = query.filter(models.Project.visibility == visibility)
    if year: query = query.filter(models.Project.year == year)
    if insect_group: query = query.filter(models.Project.insect_group.ilike(f"%{insect_group}%"))
    if locality: query = query.filter(models.Project.locality.ilike(f"%{locality}%"))
    projects = query.order_by(models.Project.year.desc(), models.Project.id).all()
    return [project_output(p, ctx) for p in projects]


@lab_router.put("/projects/{project_id}", response_model=schemas.ProjectResponse)
def update_project(project_id: int, data: schemas.ProjectUpdate, db: Session = Depends(get_db), ctx: Context = Depends(require_member)):
    db_project = get_visible_project(db, ctx, project_id)
    changes = data.model_dump(exclude_unset=True)
    # an explicit null never clears the visibility: a project is always private, unlisted or public
    new_visibility = changes.pop("visibility", None)
    for key, value in changes.items():
        setattr(db_project, key, value)
    if new_visibility:
        set_visibility(db_project, new_visibility)
    db.commit()
    db.refresh(db_project)
    return db_project


# deleting a project deletes its specimens too, so only a laboratory admin can do it
@lab_router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db), ctx: Context = Depends(require_admin)):
    db.delete(get_visible_project(db, ctx, project_id))
    db.commit()
    return None


# --- Share links ---
# an unlisted project opens only with its random share token, which works without any laboratory in the
# address. A wrong token, and a project that is not unlisted, get the same 404
def get_shared_project(db: Session, token: str) -> models.Project:
    project = db.query(models.Project).filter(
        models.Project.share_token == token, models.Project.visibility == "unlisted"
    ).first()
    if project is None:
        raise api_error(404, "project_not_found")
    return project


@app.get("/shared/{token}", response_model=schemas.SharedProjectResponse)
def shared_project(token: str, db: Session = Depends(get_db)):
    project = schemas.SharedProjectResponse.model_validate(get_shared_project(db, token))
    project.share_token = None
    return project


@app.get("/shared/{token}/specimens")
def shared_specimens(token: str, db: Session = Depends(get_db)):
    project = get_shared_project(db, token)
    query = db.query(models.Specimen).filter(models.Specimen.project_id == project.id)
    specimens = query.options(selectinload(models.Specimen.measurements)).order_by(
        models.Specimen.insect_order, models.Specimen.species, models.Specimen.catalog_number
    ).all()
    return [specimen_output(s, False) for s in specimens]


# --- Specimen routes ---
# whoever is not a member receives the specimen without the internal fields; they are removed here, on the server
def specimen_output(specimen: models.Specimen, is_member: bool) -> dict:
    exclude = None if is_member else schemas.INTERNAL_FIELDS
    return schemas.SpecimenResponse.model_validate(specimen).model_dump(mode="json", exclude=exclude)


def replace_measurements(specimen: models.Specimen, measurements):
    specimen.measurements.clear()
    for m in measurements:
        specimen.measurements.append(models.Measurement(**m.model_dump()))


@lab_router.post("/specimens", response_model=schemas.SpecimenResponse, status_code=201)
def create_specimen(specimen: schemas.SpecimenCreate, db: Session = Depends(get_db), ctx: Context = Depends(require_member)):
    # the project has to be one of this laboratory
    if specimen.project_id is not None:
        get_visible_project(db, ctx, specimen.project_id)
    if db.query(models.Specimen).filter(
        models.Specimen.laboratory_id == ctx.laboratory.id, models.Specimen.catalog_number == specimen.catalog_number
    ).first():
        raise api_error(400, "duplicate_catalog_number")
    db_specimen = models.Specimen(**specimen.model_dump(exclude={"measurements"}), laboratory_id=ctx.laboratory.id)
    replace_measurements(db_specimen, specimen.measurements or [])
    db.add(db_specimen)
    db.commit()
    db.refresh(db_specimen)
    return db_specimen


@lab_router.get("/specimens")
def list_specimens(
    species: Optional[str] = None, project_id: Optional[int] = None,
    ctx: Context = Depends(get_context), db: Session = Depends(get_db)
):
    query = visible_specimens(db, ctx).options(selectinload(models.Specimen.measurements))
    if species: query = query.filter(models.Specimen.species.ilike(f"%{species}%"))
    if project_id: query = query.filter(models.Specimen.project_id == project_id)
    specimens = query.order_by(models.Specimen.insect_order, models.Specimen.species, models.Specimen.catalog_number).all()
    return [specimen_output(s, ctx.is_member) for s in specimens]


@lab_router.put("/specimens/{specimen_id}", response_model=schemas.SpecimenResponse)
def update_specimen(specimen_id: int, data: schemas.SpecimenUpdate, db: Session = Depends(get_db), ctx: Context = Depends(require_member)):
    specimen = get_visible_specimen(db, ctx, specimen_id)

    required = {"catalog_number", "insect_order", "species"}
    fields = {
        k: v for k, v in data.model_dump(exclude_unset=True, exclude={"measurements"}).items()
        if not (v is None and k in required)
    }
    if fields.get("project_id") is not None:
        get_visible_project(db, ctx, fields["project_id"])
    new_number = fields.get("catalog_number")
    if new_number and new_number != specimen.catalog_number:
        if db.query(models.Specimen).filter(
            models.Specimen.laboratory_id == ctx.laboratory.id,
            models.Specimen.catalog_number == new_number,
            models.Specimen.id != specimen.id,
        ).first():
            raise api_error(400, "duplicate_catalog_number")
    for key, value in fields.items():
        setattr(specimen, key, value)

    # measurements sent replace the previous ones; if none are sent, they stay as they are
    if data.measurements is not None:
        replace_measurements(specimen, data.measurements)
    db.commit()
    db.refresh(specimen)
    return specimen


@lab_router.delete("/specimens/{specimen_id}", status_code=204)
def delete_specimen(specimen_id: int, db: Session = Depends(get_db), ctx: Context = Depends(require_member)):
    db.delete(get_visible_specimen(db, ctx, specimen_id))
    db.commit()
    return None


# --- Bulk import ---


@lab_router.post("/specimens/import", response_model=schemas.ImportReport)
def import_specimens(
    payload: schemas.ImportRequest, dry_run: bool = False, validate_names: bool = True,
    db: Session = Depends(get_db), ctx: Context = Depends(require_member)
):
    # everything imported goes into the laboratory of the request, and only its projects can be used
    if payload.project_id is not None:
        get_visible_project(db, ctx, payload.project_id)
    lab_id = ctx.laboratory.id
    project_ids = {p.id for p in visible_projects(db, ctx).with_entities(models.Project.id)}
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

    # duplicates are looked up only inside this laboratory: another laboratory's specimens are never touched
    existing = {}
    numbers = sorted(seen)
    for i in range(0, len(numbers), 500):
        for found in db.query(models.Specimen).filter(
            models.Specimen.laboratory_id == lab_id, models.Specimen.catalog_number.in_(numbers[i:i + 500])
        ).all():
            existing[found.catalog_number] = found

    created = updated = skipped = 0
    for line, item in valid:
        current = existing.get(item.catalog_number)
        if current is None:
            created += 1
            if not dry_run and not errors:
                new = models.Specimen(**item.model_dump(exclude={"measurements"}), laboratory_id=lab_id)
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


@lab_router.post("/taxonomy/validate", response_model=List[schemas.ValidatedName])
def validate_scientific_names(
    payload: schemas.ValidateNamesRequest, db: Session = Depends(get_db), ctx: Context = Depends(require_member)
):
    results = gbif.validate_names(payload.names, db)
    return [schemas.ValidatedName(name=n, **r) for n, r in results.items()]


# --- Export ---
# the column headers are what users see in the downloaded file, so they follow the site language;
# the importer on the site understands both
BASE_COLUMNS = {
    "pt": [
        "Codigo Etiqueta", "Ordem", "Familia", "Especie", "Data Coleta", "Local Coleta", "Latitude", "Longitude",
        "Altitude (m)", "Sexo", "Estagio", "Determinador", "Data Determinacao", "Metodo Coleta", "Habitat",
        "Imagem", "Projeto", "Notas",
    ],
    "en": [
        "Catalog Number", "Order", "Family", "Species", "Collection Date", "Locality", "Latitude", "Longitude",
        "Elevation (m)", "Sex", "Life Stage", "Identified By", "Identification Date", "Sampling Method", "Habitat",
        "Image", "Project", "Notes",
    ],
}
# only present in the full CSV, which requires login
INTERNAL_COLUMNS = {
    "pt": ["Coletor", "Numero Campo", "Localizacao Fisica", "Emprestimo", "Emprestado Para", "Data Emprestimo", "Notas Internas"],
    "en": ["Collector", "Field Number", "Storage Location", "Loan Status", "Loaned To", "Loan Date", "Internal Notes"],
}
CSV_FILE_NAMES = {
    "pt": ("acervo_entomobase.csv", "acervo_entomobase_completo.csv"),
    "en": ("entomobase_collection.csv", "entomobase_collection_full.csv"),
}


@lab_router.get("/export/csv")
def export_specimens_csv(
    project_id: Optional[int] = None, full: bool = False, lang: str = Query("pt", pattern="^(pt|en)$"),
    ctx: Context = Depends(get_context), db: Session = Depends(get_db)
):
    # the full file has the internal columns, so it is for members; the normal one is public data only,
    # even when a member asks for it
    if full and ctx.user is None:
        raise api_error(401, "full_csv_requires_login")
    if full and not ctx.is_member:
        raise api_error(403, "forbidden")
    query = (visible_specimens(db, ctx) if full else public_specimens(db, ctx.laboratory.id)).options(
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
    header = BASE_COLUMNS[lang] + (INTERNAL_COLUMNS[lang] if full else [])
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
    name = CSV_FILE_NAMES[lang][1 if full else 0]
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={name}"},
    )


# --- Darwin Core ---
# institution, collection and license come from the laboratory being exported
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


# the Darwin Core export is always public: only public projects and no internal field
@lab_router.get("/export/dwc")
def export_darwin_core(project_id: Optional[int] = None, ctx: Context = Depends(get_context), db: Session = Depends(get_db)):
    lab = ctx.laboratory
    query = public_specimens(db, lab.id).options(
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
        occurrence_id = f"{lab.institution}:{lab.collection_code}:{s.catalog_number}"
        has_coordinates = s.latitude is not None and s.longitude is not None
        occurrence_writer.writerow([
            occurrence_id, "PreservedSpecimen", lab.institution, lab.collection_code, s.catalog_number,
            s.project.title if s.project else "", lab.license, "Animalia", "Insecta", s.insect_order,
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
@lab_router.get("/demo/image/{file_name}")
def demo_image(file_name: str, db: Session = Depends(get_db), ctx: Context = Depends(get_context)):
    # only public specimens have a demo image: a browser <img> cannot send the login header
    s = public_specimens(db, ctx.laboratory.id).filter(models.Specimen.image_file == file_name).first()
    if not s:
        raise api_error(404, "image_not_found")
    svg = render_svg(s.insect_order, s.family or "", s.species, s.id, s.catalog_number, s.sex or "")
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


# included last, once every route above has been declared
app.include_router(lab_router)
app.include_router(lab_router, prefix="/labs/{slug}")
app.include_router(members_router, prefix="/labs/{slug}")
