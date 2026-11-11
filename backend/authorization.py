import secrets
from dataclasses import dataclass
from typing import Optional

import jwt
from fastapi import Depends, Header
from sqlalchemy.orm import Session

import models
from database import get_db
from errors import api_error
from laboratories import default_laboratory
from settings import ALGORITHM, SECRET_KEY


# who is asking and what they may do in the laboratory the request is about.
# The role always comes from the database (memberships), never from the token, so removing
# someone from a laboratory takes effect on their very next request
@dataclass
class Context:
    laboratory: models.Laboratory
    user: Optional[models.User] = None
    role: Optional[str] = None

    @property
    def is_member(self) -> bool:
        return self.role is not None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


# the user behind a valid token, or None; a token for a user that no longer exists is not valid
def user_from_token(authorization: Optional[str], db: Session) -> Optional[models.User]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        claims = jwt.decode(authorization.split(" ")[1], SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    return db.query(models.User).filter(models.User.email == claims.get("sub")).first()


def optional_user(authorization: str = Header(None), db: Session = Depends(get_db)) -> Optional[models.User]:
    return user_from_token(authorization, db)


# no token at all, or a token that is expired, forged or from a user that no longer exists
def unauthenticated(authorization: Optional[str]):
    if not authorization or not authorization.startswith("Bearer "):
        return api_error(401, "missing_token")
    return api_error(401, "session_expired")


def required_user(authorization: str = Header(None), db: Session = Depends(get_db)) -> models.User:
    user = user_from_token(authorization, db)
    if user is None:
        raise unauthenticated(authorization)
    return user


def role_in(db: Session, user: Optional[models.User], laboratory: models.Laboratory) -> Optional[str]:
    if user is None:
        return None
    membership = db.query(models.Membership).filter_by(user_id=user.id, laboratory_id=laboratory.id).first()
    return membership.role if membership else None


# the only place that decides which laboratory a request is about. Until the routes carry the
# laboratory in the address (phase 3 of the plan) it is the first one; phase 3 changes only this function
def resolve_laboratory(db: Session) -> models.Laboratory:
    return default_laboratory(db)


def get_context(user: Optional[models.User] = Depends(optional_user), db: Session = Depends(get_db)) -> Context:
    laboratory = resolve_laboratory(db)
    return Context(laboratory=laboratory, user=user, role=role_in(db, user, laboratory))


# a member of the laboratory (researcher or admin)
def require_member(ctx: Context = Depends(get_context), authorization: str = Header(None)) -> Context:
    if ctx.user is None:
        raise unauthenticated(authorization)
    if not ctx.is_member:
        raise api_error(403, "forbidden")
    return ctx


def require_admin(ctx: Context = Depends(require_member)) -> Context:
    if not ctx.is_admin:
        raise api_error(403, "forbidden")
    return ctx


def require_superadmin(user: models.User = Depends(required_user)) -> models.User:
    if not user.is_superadmin:
        raise api_error(403, "forbidden")
    return user


# ---------- the only way to read data ----------
# Every query for projects and specimens starts here. A member sees everything in their laboratory;
# anyone else sees only what is public. Unlisted projects (open only with the share link) and specimens
# without a project are never shown to non-members, so they cannot leak into lists, searches or exports.
def public_projects(db: Session, laboratory_id: int):
    return db.query(models.Project).filter(
        models.Project.laboratory_id == laboratory_id, models.Project.visibility == "public"
    )


def public_specimens(db: Session, laboratory_id: int):
    return db.query(models.Specimen).join(models.Project, models.Specimen.project_id == models.Project.id).filter(
        models.Specimen.laboratory_id == laboratory_id, models.Project.visibility == "public"
    )


def visible_projects(db: Session, ctx: Context):
    if ctx.is_member:
        return db.query(models.Project).filter(models.Project.laboratory_id == ctx.laboratory.id)
    return public_projects(db, ctx.laboratory.id)


def visible_specimens(db: Session, ctx: Context):
    if ctx.is_member:
        return db.query(models.Specimen).filter(models.Specimen.laboratory_id == ctx.laboratory.id)
    return public_specimens(db, ctx.laboratory.id)


# a project of the laboratory that the person may see, or a 404: asking for something that exists but is
# hidden gets the same answer as asking for something that does not exist
def get_visible_project(db: Session, ctx: Context, project_id: int) -> models.Project:
    project = visible_projects(db, ctx).filter(models.Project.id == project_id).first()
    if project is None:
        raise api_error(404, "project_not_found")
    return project


def get_visible_specimen(db: Session, ctx: Context, specimen_id: int) -> models.Specimen:
    specimen = visible_specimens(db, ctx).filter(models.Specimen.id == specimen_id).first()
    if specimen is None:
        raise api_error(404, "specimen_not_found")
    return specimen


# ---------- share links ----------
def new_share_token() -> str:
    return secrets.token_urlsafe(24)


# applies a visibility to a project. The share token exists only while the project is unlisted:
# leaving that state kills the old link, and becoming unlisted again creates a different one
def set_visibility(project: models.Project, visibility: str) -> None:
    project.visibility = visibility
    if visibility == "unlisted":
        if not project.share_token:
            project.share_token = new_share_token()
    else:
        project.share_token = None
