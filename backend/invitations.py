from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session

import models
from email_confirmation import hash_code, new_code, site_url, utc_now
from mailer import send_email

# how long the link in the invitation works
INVITATION_VALID_DAYS = 7

ROLE_NAMES = {"admin": ("administrador(a)", "admin"), "researcher": ("pesquisador(a)", "researcher")}


# creates the invitation of this address to this laboratory, or replaces the one it already had (new code,
# role and deadline), so only the newest e-mail works. Returns the code, which is never stored
def issue_invitation(db: Session, laboratory: models.Laboratory, email: str, role: str, invited_by: models.User) -> tuple:
    code = new_code()
    now = utc_now()
    invitation = db.query(models.Invitation).filter_by(laboratory_id=laboratory.id, email=email).first()
    if invitation is None:
        invitation = models.Invitation(laboratory_id=laboratory.id, email=email)
        db.add(invitation)
    invitation.role, invitation.invited_by_id, invitation.code_hash = role, invited_by.id, hash_code(code)
    invitation.created_at, invitation.expires_at = now, now + timedelta(days=INVITATION_VALID_DAYS)
    db.flush()
    return invitation, code


# the invitation behind a code, if it can still be used: not expired, and sent by someone who is still an
# admin of that laboratory (removing an admin, or taking the role away, also ends what they sent)
def usable_invitation(db: Session, code: str) -> Optional[models.Invitation]:
    invitation = db.query(models.Invitation).filter(models.Invitation.code_hash == hash_code(code)).first()
    if invitation is None or invitation.expires_at <= utc_now():
        return None
    still_admin = db.query(models.Membership).filter_by(
        user_id=invitation.invited_by_id, laboratory_id=invitation.laboratory_id, role="admin"
    ).first()
    return invitation if still_admin else None


# in Portuguese and English at once, like the confirmation e-mail: the person has not chosen a language yet.
# The subject is fixed, so nothing typed by an admin goes into a header
def send_invitation(invitation: models.Invitation, code: str) -> None:
    link = f"{site_url()}/#/invite/{code}"
    lab = invitation.laboratory.name
    who = invitation.invited_by.name or invitation.invited_by.email
    role_pt, role_en = ROLE_NAMES[invitation.role]
    send_email(invitation.email, "EntomoBase: convite para um laboratório / invitation to a laboratory", (
        "Olá!\n\n"
        f"{who} convidou você para o laboratório \"{lab}\" no EntomoBase, como {role_pt}.\n"
        f"Para aceitar, abra o link abaixo (vale por {INVITATION_VALID_DAYS} dias):\n{link}\n\n"
        "Se você não esperava este convite, ignore esta mensagem.\n\n"
        "---\n\n"
        "Hello!\n\n"
        f"{who} invited you to the laboratory \"{lab}\" on EntomoBase, as {role_en}.\n"
        f"To accept, open the link below (valid for {INVITATION_VALID_DAYS} days):\n{link}\n\n"
        "If you did not expect this invitation, ignore this message.\n"
    ))
