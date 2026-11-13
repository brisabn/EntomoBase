import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

import models
from mailer import MailError, send_email

# how long the link in the e-mail works: confirming an address, and choosing a new password (shorter, since
# it opens an account that already exists)
CODE_VALID_HOURS = 24
RESET_VALID_HOURS = 1
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
def issue_code(db: Session, user: models.User, hours: int = CODE_VALID_HOURS) -> str:
    db.query(models.EmailConfirmation).filter(models.EmailConfirmation.user_id == user.id).delete()
    code = new_code()
    now = utc_now()
    db.add(models.EmailConfirmation(user_id=user.id, code_hash=hash_code(code), created_at=now, expires_at=now + timedelta(hours=hours)))
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


def send_password_reset(email: str, code: str) -> None:
    link = f"{site_url()}/#/new-password/{code}"
    send_email(email, "EntomoBase: escolha uma nova senha / choose a new password", (
        "Olá!\n\n"
        f"Para escolher uma nova senha no EntomoBase, abra o link abaixo (vale por {RESET_VALID_HOURS} hora):\n{link}\n\n"
        "Se você não pediu isso, ignore esta mensagem: sua senha continua a mesma.\n\n"
        "---\n\n"
        "Hello!\n\n"
        f"To choose a new password on EntomoBase, open the link below (valid for {RESET_VALID_HOURS} hour):\n{link}\n\n"
        "If you did not ask for this, ignore this message: your password stays the same.\n"
    ))


# sent when someone asks for a new password for an address with no account, so the response of the site is the
# same either way; the person who mistyped the address also learns why no link came
def send_no_account(email: str) -> None:
    send_email(email, "EntomoBase: pedido de nova senha / new password request", (
        "Olá!\n\n"
        "Alguém pediu uma nova senha no EntomoBase para este e-mail, mas não há conta com ele. "
        "Se foi você, talvez tenha usado outro e-mail. Se não foi, ignore esta mensagem.\n\n"
        "---\n\n"
        "Hello!\n\n"
        "Someone asked for a new EntomoBase password for this e-mail, but there is no account with it. "
        "If it was you, you may have used another e-mail. If not, ignore this message.\n"
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
