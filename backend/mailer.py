import os
import re
import smtplib
import ssl
import sys
from email.message import EmailMessage
from typing import List

# Sends the e-mails the platform needs (confirmation links, approvals). Everything is read from the
# environment each time a message is sent, so nothing has to be configured to start the API:
#   MAIL_BACKEND   smtp | mailpit | console | memory   (console is the default in development, memory is for the tests)
#   MAIL_FROM      the sender address
#   SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD, SMTP_SECURITY (starttls | ssl | none; starttls by default)
# mailpit is a shortcut for development: Mailpit (https://mailpit.axllent.org) running on this computer, which
# keeps every e-mail in an inbox in the browser (http://localhost:8025) and delivers nothing. It is SMTP to
# 127.0.0.1:1025 without encryption or login; SMTP_HOST and SMTP_PORT still change where it is
MAILPIT = {"host": "127.0.0.1", "port": "1025", "security": "none"}


class MailError(Exception):
    pass


# messages "sent" by the memory backend, so a test can read what would have been e-mailed
outbox: List[EmailMessage] = []

SMTP_TIMEOUT_SECONDS = 10
# deliberately simple: one address, no spaces, no angle brackets or line breaks that could add headers
ADDRESS_PATTERN = re.compile(r"^[^\s@<>,;\"']+@[^\s@<>,;\"']+\.[^\s@<>,;\"']+$")


def valid_address(address: str) -> bool:
    return bool(ADDRESS_PATTERN.match(address or ""))


def backend_name() -> str:
    name = os.getenv("MAIL_BACKEND", "").strip().lower()
    if not name and os.getenv("ENTOMOBASE_ENV") == "dev":
        name = "console"
    return name


def build_message(to: str, subject: str, body: str, sender: str) -> EmailMessage:
    if not valid_address(to):
        raise MailError("invalid recipient address")
    if not valid_address(sender):
        raise MailError("MAIL_FROM is not set to a valid address")
    # header values with a line break would let a caller add headers (or recipients) of their own
    if "\n" in subject or "\r" in subject:
        raise MailError("the subject cannot have line breaks")
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body, charset="utf-8")
    return message


def send_with_smtp(message: EmailMessage, mailpit: bool = False) -> None:
    host = os.getenv("SMTP_HOST", "").strip() or (MAILPIT["host"] if mailpit else "")
    if not host:
        raise MailError("SMTP_HOST is not set")
    security = MAILPIT["security"] if mailpit else os.getenv("SMTP_SECURITY", "starttls").strip().lower()
    if security not in ("starttls", "ssl", "none"):
        raise MailError("SMTP_SECURITY must be starttls, ssl or none")
    default_port = MAILPIT["port"] if mailpit else ("465" if security == "ssl" else "587")
    try:
        port = int(os.getenv("SMTP_PORT", "").strip() or default_port)
    except ValueError:
        raise MailError("SMTP_PORT is not a number")
    # Mailpit takes no login: a user and password set for a real server are not sent to it
    user, password = ("", "") if mailpit else (os.getenv("SMTP_USER", ""), os.getenv("SMTP_PASSWORD", ""))
    context = ssl.create_default_context()
    try:
        if security == "ssl":
            server = smtplib.SMTP_SSL(host, port, timeout=SMTP_TIMEOUT_SECONDS, context=context)
        else:
            server = smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT_SECONDS)
        with server:
            if security == "starttls":
                server.starttls(context=context)
            if user:
                server.login(user, password)
            server.send_message(message)
    except (smtplib.SMTPException, OSError) as error:
        # never echo the password or the server's answer to the user; the caller decides what to show
        raise MailError(f"could not send the e-mail ({type(error).__name__})")


# a terminal that is not UTF-8 (the Windows default) cannot show every character; those become "?" instead
# of failing the request that sent the e-mail
def print_safely(text: str) -> None:
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    sys.stdout.write(text.encode(encoding, errors="replace").decode(encoding))
    sys.stdout.flush()


def send_email(to: str, subject: str, body: str) -> None:
    name = backend_name()
    if name not in ("smtp", "mailpit", "console", "memory"):
        raise MailError("e-mail is not configured: set MAIL_BACKEND (smtp, or console or mailpit in development)")
    # only a real server needs a real sender; the others make one up
    sender = os.getenv("MAIL_FROM", "").strip() or ("" if name == "smtp" else "noreply@entomobase.invalid")
    message = build_message(to, subject, body, sender)
    if name == "memory":
        outbox.append(message)
    elif name == "console":
        print_safely(f"\n--- e-mail (console backend) ---\nTo: {to}\nSubject: {subject}\n\n{body}\n--- end ---\n")
    else:
        send_with_smtp(message, mailpit=name == "mailpit")
