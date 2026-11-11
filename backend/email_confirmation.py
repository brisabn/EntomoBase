import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

import models
from mailer import MailError, send_email

# how long the link in the e-mail works
CODE_VALID_HOURS = 24
# where the site runs while developing; anywhere else SITE_URL has to say
DEV_SITE_URL = "http://127.0.0.1:5500"


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_code() -> str:
    return secrets.token_urlsafe(32)


# the code is random and long, so a plain hash is enough (unlike a password, there is nothing to guess)
def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def site_url() -> str:
    url = os.getenv("SITE_URL", "").strip().rstrip("/")
    if url:
        return url
    if os.getenv("ENTOMOBASE_ENV") == "dev":
        return DEV_SITE_URL
    raise MailError("SITE_URL is not set")


# a new code replaces the ones the user still had, so only the last e-mail works
def issue_code(db: Session, user: models.User) -> str:
    db.query(models.EmailConfirmation).filter(models.EmailConfirmation.user_id == user.id).delete()
    code = new_code()
    now = utc_now()
    db.add(models.EmailConfirmation(user_id=user.id, code_hash=hash_code(code), created_at=now, expires_at=now + timedelta(hours=CODE_VALID_HOURS)))
    return code


# e-mails are in Portuguese and English at once: the person has not chosen a language yet
def send_confirmation(email: str, code: str) -> None:
    link = f"{site_url()}/#/confirm/{code}"
    send_email(email, "EntomoBase: confirme seu e-mail / confirm your e-mail", (
        "Olá!\n\n"
        f"Para confirmar seu e-mail no EntomoBase, abra o link abaixo (vale por {CODE_VALID_HOURS} horas):\n{link}\n\n"
        "Se não foi você, ignore esta mensagem.\n\n"
        "---\n\n"
        "Hello!\n\n"
        f"To confirm your e-mail on EntomoBase, open the link below (valid for {CODE_VALID_HOURS} hours):\n{link}\n\n"
        "If this was not you, ignore this message.\n"
    ))


# sent when someone signs up with an address that already has an account, so the response of the site
# does not have to tell the person who asked (it could be anyone) whether the address is registered
def send_already_registered(email: str) -> None:
    send_email(email, "EntomoBase: você já tem uma conta / you already have an account", (
        "Olá!\n\n"
        "Alguém tentou criar uma conta no EntomoBase com este e-mail, mas ele já tem uma. "
        "Se foi você, é só entrar com o seu e-mail e a sua senha. Se não foi, ignore esta mensagem.\n\n"
        "---\n\n"
        "Hello!\n\n"
        "Someone tried to create an EntomoBase account with this e-mail, but it already has one. "
        "If it was you, just sign in with your e-mail and password. If not, ignore this message.\n"
    ))
