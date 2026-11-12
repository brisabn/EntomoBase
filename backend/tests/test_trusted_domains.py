import pytest

import trusted_domains
from trusted_domains import is_trusted


@pytest.fixture(autouse=True)
def no_setting(monkeypatch):
    monkeypatch.delenv("TRUSTED_EMAIL_DOMAINS", raising=False)


def configure(monkeypatch, value):
    monkeypatch.setenv("TRUSTED_EMAIL_DOMAINS", value)


def test_ufmg_is_trusted_by_default():
    assert trusted_domains.trusted_domains() == {"ufmg.br"}
    assert is_trusted("pessoa@ufmg.br")


def test_a_subdomain_is_covered():
    assert is_trusted("pessoa@icb.ufmg.br") and is_trusted("pessoa@a.b.ufmg.br")


@pytest.mark.parametrize("email", ["pessoa@notufmg.br", "pessoa@ufmg.br.evil.com", "pessoa@ufmg.com", "pessoa@gmail.com", "ufmg.br@gmail.com"])
def test_lookalikes_are_not_trusted(email):
    assert not is_trusted(email)


def test_case_and_a_trailing_dot_do_not_matter():
    assert is_trusted("Pessoa@ICB.UFMG.BR") and is_trusted("pessoa@ufmg.br.")


@pytest.mark.parametrize("email", ["", None, "no-at-sign", "pessoa@"])
def test_something_that_is_not_an_address_is_not_trusted(email):
    assert not is_trusted(email)


def test_the_list_comes_from_the_environment(monkeypatch):
    configure(monkeypatch, " USP.br , @unicamp.br, .fiocruz.br ,, ")
    assert trusted_domains.trusted_domains() == {"usp.br", "unicamp.br", "fiocruz.br"}
    assert is_trusted("a@usp.br") and is_trusted("a@ib.unicamp.br") and is_trusted("a@fiocruz.br")
    assert not is_trusted("a@ufmg.br")


def test_an_empty_setting_trusts_nobody(monkeypatch):
    configure(monkeypatch, "")
    assert trusted_domains.trusted_domains() == set()
    assert not is_trusted("pessoa@ufmg.br")


@pytest.mark.parametrize("entry", ["br", "edu.br", "com.br", "gov.br", "org.br", "net.br", "com", "edu", "ufmg br", "ufmg .br", "*"])
def test_shared_suffixes_and_malformed_entries_are_ignored(monkeypatch, entry):
    configure(monkeypatch, f"{entry},usp.br")
    assert trusted_domains.trusted_domains() == {"usp.br"}
    assert not is_trusted("pessoa@qualquer.edu.br") and not is_trusted("pessoa@empresa.com.br")


def test_the_domain_of_an_address():
    assert trusted_domains.domain_of("a@B.Ufmg.br") == "b.ufmg.br"
    assert trusted_domains.domain_of("odd@name@ufmg.br") == "ufmg.br"
    assert trusted_domains.domain_of("nothing") == ""
