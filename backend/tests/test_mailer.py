import smtplib

import pytest

import mailer
from mailer import MailError, send_email

SMTP_ENV = {"MAIL_BACKEND": "smtp", "MAIL_FROM": "entomobase@example.org", "SMTP_HOST": "smtp.example.org"}


@pytest.fixture(autouse=True)
def clean_mail_environment(monkeypatch):
    for name in ("MAIL_BACKEND", "MAIL_FROM", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_SECURITY", "ENTOMOBASE_ENV"):
        monkeypatch.delenv(name, raising=False)
    mailer.outbox.clear()


def configure(monkeypatch, **values):
    for name, value in values.items():
        monkeypatch.setenv(name, value)


# a stand-in for smtplib that records what a real server would have received
class FakeServer:
    instances = []
    fail_with = None

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.timeout, self.context = host, port, timeout, context
        self.calls = []
        self.sent = []
        FakeServer.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self, context=None):
        self.calls.append("starttls")
        self.tls_context = context

    def login(self, user, password):
        self.calls.append(("login", user, password))

    def send_message(self, message):
        if FakeServer.fail_with:
            raise FakeServer.fail_with
        self.sent.append(message)


@pytest.fixture
def fake_smtp(monkeypatch):
    FakeServer.instances = []
    FakeServer.fail_with = None
    monkeypatch.setattr(smtplib, "SMTP", FakeServer)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeServer)
    return FakeServer


# ---------- choosing the backend ----------
def test_nothing_configured_refuses_to_send(monkeypatch):
    with pytest.raises(MailError, match="not configured"):
        send_email("a@example.org", "Hi", "text")


def test_an_unknown_backend_is_refused(monkeypatch):
    configure(monkeypatch, MAIL_BACKEND="pigeon")
    with pytest.raises(MailError, match="not configured"):
        send_email("a@example.org", "Hi", "text")


def test_development_mode_defaults_to_the_console(monkeypatch, capsys):
    configure(monkeypatch, ENTOMOBASE_ENV="dev")
    send_email("a@example.org", "Confirm", "Open this link: http://x.test/abc")
    out = capsys.readouterr().out
    assert "To: a@example.org" in out and "Subject: Confirm" in out and "http://x.test/abc" in out


def test_the_backend_name_ignores_case_and_spaces(monkeypatch):
    configure(monkeypatch, MAIL_BACKEND="  MEMORY ")
    send_email("a@example.org", "Hi", "text")
    assert len(mailer.outbox) == 1


def test_production_without_configuration_does_not_fall_back_to_the_console(monkeypatch, capsys):
    configure(monkeypatch, ENTOMOBASE_ENV="prod")
    with pytest.raises(MailError):
        send_email("a@example.org", "Hi", "link")
    assert capsys.readouterr().out == ""


# ---------- the message ----------
def test_the_memory_backend_keeps_the_message(monkeypatch):
    configure(monkeypatch, MAIL_BACKEND="memory", MAIL_FROM="entomobase@example.org")
    send_email("person@example.org", "Subject line", "Body with açúcar and 日本")
    message = mailer.outbox[0]
    assert (message["To"], message["From"], message["Subject"]) == ("person@example.org", "entomobase@example.org", "Subject line")
    assert "açúcar" in message.get_content() and "日本" in message.get_content()


def test_the_console_and_memory_backends_make_up_a_sender(monkeypatch):
    configure(monkeypatch, MAIL_BACKEND="memory")
    send_email("a@example.org", "Hi", "text")
    assert mailer.outbox[0]["From"] == "noreply@entomobase.invalid"


@pytest.mark.parametrize("address", ["", "nobody", "a@b", "a b@example.org", "a@example.org, b@example.org", "<a@example.org>",
                                     "a@example.org\nBcc: x@example.org", "a@example.org;b@example.org", "\"a\"@example.org", None])
def test_a_recipient_that_is_not_a_single_plain_address_is_refused(monkeypatch, address):
    configure(monkeypatch, MAIL_BACKEND="memory")
    with pytest.raises(MailError, match="recipient"):
        send_email(address, "Hi", "text")
    assert mailer.outbox == []


@pytest.mark.parametrize("subject", ["Hi\nBcc: x@example.org", "Hi\rBcc: x@example.org"])
def test_a_subject_with_a_line_break_cannot_add_headers(monkeypatch, subject):
    configure(monkeypatch, MAIL_BACKEND="memory")
    with pytest.raises(MailError, match="line breaks"):
        send_email("a@example.org", subject, "text")
    assert mailer.outbox == []


def test_the_configured_sender_must_be_an_address(monkeypatch):
    configure(monkeypatch, MAIL_BACKEND="memory", MAIL_FROM="not an address")
    with pytest.raises(MailError, match="MAIL_FROM"):
        send_email("a@example.org", "Hi", "text")


def test_valid_address():
    assert mailer.valid_address("first.last+tag@sub.example.org")
    assert not mailer.valid_address("") and not mailer.valid_address(None)


# ---------- SMTP ----------
def test_smtp_uses_starttls_and_the_login(monkeypatch, fake_smtp):
    configure(monkeypatch, **SMTP_ENV, SMTP_USER="user", SMTP_PASSWORD="secret")
    send_email("person@example.org", "Hi", "text")
    server = fake_smtp.instances[0]
    assert (server.host, server.port, server.timeout) == ("smtp.example.org", 587, mailer.SMTP_TIMEOUT_SECONDS)
    assert server.calls == ["starttls", ("login", "user", "secret")]
    assert server.sent[0]["To"] == "person@example.org" and server.tls_context is not None


def test_smtp_without_a_login_skips_it(monkeypatch, fake_smtp):
    configure(monkeypatch, **SMTP_ENV)
    send_email("person@example.org", "Hi", "text")
    assert fake_smtp.instances[0].calls == ["starttls"]


def test_smtp_over_ssl_uses_its_own_port_and_no_starttls(monkeypatch, fake_smtp):
    configure(monkeypatch, **SMTP_ENV, SMTP_SECURITY="ssl")
    send_email("person@example.org", "Hi", "text")
    server = fake_smtp.instances[0]
    assert server.port == 465 and server.calls == [] and server.timeout == mailer.SMTP_TIMEOUT_SECONDS
    assert server.context is not None


def test_smtp_without_encryption_only_when_asked(monkeypatch, fake_smtp):
    configure(monkeypatch, **SMTP_ENV, SMTP_SECURITY="none", SMTP_PORT="25")
    send_email("person@example.org", "Hi", "text")
    server = fake_smtp.instances[0]
    assert server.port == 25 and server.calls == []


def test_an_unknown_security_mode_is_refused(monkeypatch, fake_smtp):
    configure(monkeypatch, **SMTP_ENV, SMTP_SECURITY="plain")
    with pytest.raises(MailError, match="SMTP_SECURITY"):
        send_email("person@example.org", "Hi", "text")
    assert fake_smtp.instances == []


def test_smtp_needs_a_host_and_a_port_that_is_a_number(monkeypatch, fake_smtp):
    configure(monkeypatch, MAIL_BACKEND="smtp", MAIL_FROM="entomobase@example.org")
    with pytest.raises(MailError, match="SMTP_HOST"):
        send_email("person@example.org", "Hi", "text")
    configure(monkeypatch, **SMTP_ENV, SMTP_PORT="abc")
    with pytest.raises(MailError, match="SMTP_PORT"):
        send_email("person@example.org", "Hi", "text")


def test_smtp_needs_a_real_sender(monkeypatch, fake_smtp):
    configure(monkeypatch, MAIL_BACKEND="smtp", SMTP_HOST="smtp.example.org")
    with pytest.raises(MailError, match="MAIL_FROM"):
        send_email("person@example.org", "Hi", "text")
    assert fake_smtp.instances == []


@pytest.mark.parametrize("failure", [smtplib.SMTPAuthenticationError(535, b"bad password hunter2"), smtplib.SMTPRecipientsRefused({}), ConnectionRefusedError("no"), TimeoutError("slow")])
def test_a_failing_server_becomes_a_mail_error_that_does_not_leak_details(monkeypatch, fake_smtp, failure):
    configure(monkeypatch, **SMTP_ENV, SMTP_USER="user", SMTP_PASSWORD="hunter2")
    fake_smtp.fail_with = failure
    with pytest.raises(MailError) as error:
        send_email("person@example.org", "Hi", "text")
    assert "hunter2" not in str(error.value) and "could not send" in str(error.value)


def test_the_connection_itself_failing_is_also_a_mail_error(monkeypatch):
    def refuse(*args, **kwargs):
        raise ConnectionRefusedError("nobody home")
    monkeypatch.setattr(smtplib, "SMTP", refuse)
    configure(monkeypatch, **SMTP_ENV)
    with pytest.raises(MailError, match="could not send"):
        send_email("person@example.org", "Hi", "text")
