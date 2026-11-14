from typing import List, Optional

from sqlalchemy.orm import Session

import models
from email_confirmation import site_url, utc_now
from laboratories import DEFAULT_LABORATORY
from mailer import send_email

# how many requests one account may make in a day, counting the ones approved at once by the e-mail domain:
# a trusted address must not be able to open laboratories in bulk
REQUESTS_PER_DAY = 3


# the platform administrators who can read e-mail: an unconfirmed address may not even be theirs
def platform_admin_emails(db: Session) -> List[str]:
    rows = db.query(models.User.email).filter(
        models.User.is_superadmin == True, models.User.email_verified_at.isnot(None)
    ).order_by(models.User.email).all()
    return [email for (email,) in rows]


# creates the laboratory of the request, with whoever asked as its only member and admin, and marks the request
# approved. decided_by is None when the e-mail domain approved it. The caller commits (a slug taken at the same
# moment fails on the flush, as an IntegrityError)
def open_laboratory(db: Session, request: models.LaboratoryRequest, decided_by: Optional[models.User], listed: bool) -> models.Laboratory:
    laboratory = models.Laboratory(
        slug=request.slug, name=request.name, institution=request.institution, collection_code=request.collection_code,
        license=request.license or DEFAULT_LABORATORY["license"], listed=listed,
    )
    laboratory.memberships.append(models.Membership(user_id=request.requester_id, role="admin"))
    db.add(laboratory)
    db.flush()
    request.status, request.decided_at, request.laboratory = "approved", utc_now(), laboratory
    request.decided_by_id = decided_by.id if decided_by else None
    return laboratory


def describe(request: models.LaboratoryRequest) -> str:
    requester = request.requester
    who = f"{requester.name} <{requester.email}>" if requester.name else requester.email
    lines = [
        f"{request.name} ({request.institution}, {request.collection_code})",
        f"lab/{request.slug}",
        who,
    ]
    if request.message:
        lines += ["", request.message]
    return "\n".join(lines)


# tells the platform administrators about a new request: one that waits for them, or one the e-mail domain
# already approved (so they know the laboratory exists, and can put it in the public list). The subject is fixed,
# so nothing typed by the person goes into a header
def send_new_request(db: Session, request: models.LaboratoryRequest) -> None:
    link = f"{site_url()}/#/platform"
    if request.status == "approved":
        pt = "O laboratório abaixo foi criado na hora, porque o e-mail de quem pediu é de um domínio confiável. Ele está fora da lista pública da plataforma."
        en = "The laboratory below was created at once, because the e-mail of whoever asked is from a trusted domain. It is out of the public list of the platform."
    else:
        pt = "Um novo pedido de laboratório aguarda sua decisão."
        en = "A new laboratory request is waiting for your decision."
    body = (
        f"{pt}\n\n{describe(request)}\n\nPara ver os pedidos: {link}\n\n---\n\n"
        f"{en}\n\n{describe(request)}\n\nTo see the requests: {link}\n"
    )
    for email in platform_admin_emails(db):
        send_email(email, "EntomoBase: pedido de laboratório / laboratory request", body)


# tells the person what was decided; in Portuguese and English at once, like the other e-mails
def send_decision(request: models.LaboratoryRequest) -> None:
    to = request.requester.email
    if request.status == "approved":
        link = f"{site_url()}/#/lab/{request.slug}"
        listed = request.laboratory.listed
        send_email(to, "EntomoBase: seu laboratório foi criado / your laboratory was created", (
            "Olá!\n\n"
            f"Seu pedido foi aprovado: o laboratório \"{request.name}\" foi criado, e você é a pessoa que o administra.\n"
            + ("Ele já aparece na lista pública da plataforma.\n" if listed else
               "Por enquanto ele está fora da lista pública da plataforma, mas funciona no endereço abaixo.\n")
            + f"{link}\n\n"
            "Pela página de membros você convida as outras pessoas do laboratório.\n\n"
            "---\n\n"
            "Hello!\n\n"
            f"Your request was approved: the laboratory \"{request.name}\" was created, and you are its admin.\n"
            + ("It is already in the public list of the platform.\n" if listed else
               "For now it is out of the public list of the platform, but it works at the address below.\n")
            + f"{link}\n\n"
            "On the members page you invite the other people of the laboratory.\n"
        ))
        return
    reason_pt = f"\nMotivo:\n{request.decision_reason}\n" if request.decision_reason else ""
    reason_en = f"\nReason:\n{request.decision_reason}\n" if request.decision_reason else ""
    send_email(to, "EntomoBase: pedido de laboratório recusado / laboratory request refused", (
        "Olá!\n\n"
        f"O pedido do laboratório \"{request.name}\" não foi aprovado pela administração da plataforma.\n{reason_pt}\n"
        "Você pode fazer um novo pedido pela página Minha conta.\n\n"
        "---\n\n"
        "Hello!\n\n"
        f"The request for the laboratory \"{request.name}\" was not approved by the administration of the platform.\n{reason_en}\n"
        "You can make a new request on the My account page.\n"
    ))
