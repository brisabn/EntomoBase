# Scenario 2: someone creates an account, cannot sign in before confirming the e-mail,
# opens the link of the e-mail and then signs in.
import re

from playwright.sync_api import expect

from conftest import sign_in

EMAIL = "ana.e2e@ufmg.br"
PASSWORD = "uma-senha-boa"


def test_a_new_account_signs_in_only_after_confirming_the_email(new_page, servers):
    page = new_page()
    page.goto(servers.site + "/")
    page.locator(".home-join").get_by_role("button", name="Criar conta").click()

    # the browser itself refuses a short password, and nothing is sent
    page.get_by_label("Nome").fill("Ana Teste")
    page.get_by_label("E-mail").fill(EMAIL)
    page.get_by_label("Senha").fill("curta")
    page.locator(".modal").get_by_role("button", name="Criar conta").click()
    expect(page.get_by_role("heading", name="Criar conta")).to_be_visible()
    assert servers.confirmation_links() == []

    page.get_by_label("Senha").fill(PASSWORD)
    page.locator(".modal").get_by_role("button", name="Criar conta").click()
    expect(page.get_by_role("heading", name="Confira seu e-mail")).to_be_visible()
    expect(page.locator(".modal")).to_contain_text(EMAIL)
    page.get_by_role("button", name="Fechar").click()

    # before the confirmation the sign-in is refused, with the reason
    sign_in(page, EMAIL, PASSWORD)
    expect(page.locator(".form-error")).to_contain_text("Confirme seu e-mail")
    page.get_by_role("button", name="Cancelar").click()
    expect(page.get_by_role("button", name="Sair")).to_have_count(0)

    # the link of the e-mail confirms the account and leaves the address bar
    links = servers.confirmation_links()
    assert len(links) == 1
    page.goto(links[0])
    expect(page.locator(".confirm-box")).to_contain_text("foi confirmado")
    expect(page).to_have_url(re.compile(r"#/confirmar$"))

    # now the same password works, and the home page stops inviting to sign up
    page.locator(".confirm-box button").click()
    expect(page.get_by_label("E-mail")).to_have_value(EMAIL)
    page.get_by_label("Senha").fill(PASSWORD)
    page.get_by_role("button", name="Acessar").click()
    expect(page.get_by_role("button", name="Sair")).to_be_visible()
    page.goto(servers.site + "/")
    expect(page.locator(".grid .card").first).to_be_visible()
    expect(page.locator(".home-join")).to_have_count(0)

    # the link works once: opened again in another browser, it is refused
    other = new_page()
    other.goto(links[0])
    expect(other.locator(".confirm-box .form-error")).to_contain_text("inválido ou expirou")
