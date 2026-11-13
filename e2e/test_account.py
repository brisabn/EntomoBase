# Scenario 2: accounts. Someone creates an account, cannot sign in before confirming the e-mail,
# opens the link of the e-mail and then signs in. And an admin invites someone without an account, who
# opens the link of the invitation, creates the account there and is already in the laboratory.
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


INVITED = "convidada.e2e@ufmg.br"


def test_an_invited_person_creates_the_account_joins_the_laboratory_and_can_leave(new_page, servers):
    admin = new_page()
    admin.goto(servers.site + "/#/lab/ufmg/membros")
    sign_in(admin, "admin.ufmg@entomobase.test", servers.passwords["admin.ufmg@entomobase.test"])
    # the sign-in window has an "E-mail" field too: wait for it to close and the form to appear
    expect(admin.locator(".modal")).to_have_count(0)
    expect(admin.get_by_role("heading", name="Convidar para o laboratório")).to_be_visible()
    admin.get_by_label("E-mail").fill(INVITED)
    admin.get_by_role("button", name="Enviar convite").click()
    expect(admin.get_by_role("heading", name="Convites pendentes (1)")).to_be_visible()
    expect(admin.locator(".invitation-list")).to_contain_text(INVITED)
    links = servers.invitation_links()
    assert len(links) == 1

    # the link opens without an account, and its code leaves the address bar
    guest = new_page()
    guest.goto(links[0])
    expect(guest.locator(".confirm-box")).to_contain_text("como pesquisador(a)")
    expect(guest.locator(".confirm-box")).to_contain_text(INVITED)
    expect(guest).to_have_url(re.compile(r"#/convite$"))
    # changing the language keeps the invitation open
    guest.locator(".lang-switch").click()
    expect(guest.locator(".confirm-box")).to_contain_text("as researcher")
    guest.locator(".lang-switch").click()

    guest.get_by_label("Nome").fill("Convidada Teste")
    guest.get_by_label("Senha").fill(PASSWORD)
    guest.get_by_role("button", name="Criar conta e entrar").click()
    expect(guest.locator(".confirm-box")).to_contain_text("Pronto! Agora você faz parte")
    expect(guest.get_by_role("button", name="Sair")).to_be_visible()

    # already a researcher there: the projects page offers to create one
    guest.get_by_role("link", name="Ir para o laboratório").click()
    guest.get_by_role("link", name="Projetos").first.click()
    expect(guest.get_by_role("button", name=re.compile("Novo projeto"))).to_be_visible()

    # the admin sees a member, no longer an invitation
    admin.reload()
    expect(admin.locator(".member-list").first).to_contain_text(INVITED)
    expect(admin.get_by_role("heading", name=re.compile("Convites pendentes"))).to_have_count(0)

    # the link works once
    other = new_page()
    other.goto(links[0])
    expect(other.locator(".confirm-box .form-error")).to_contain_text("já foi usado")

    # and leaves on their own, from the About page; the window says what leaving means, and the person
    # stays signed in (leaving is not signing out)
    guest.get_by_role("link", name="Sobre").first.click()
    expect(guest.get_by_role("heading", name="Sua participação")).to_be_visible()
    guest.get_by_role("button", name="Deixar o laboratório").click()
    expect(guest.get_by_role("alertdialog")).to_contain_text("Para voltar, será preciso um novo convite")
    guest.get_by_role("alertdialog").get_by_role("button", name="Deixar o laboratório").click()
    expect(guest.get_by_text("Você deixou o laboratório EntomoBase UFMG.")).to_be_visible()
    expect(guest.get_by_role("heading", name="Sua participação")).to_have_count(0)
    expect(guest.get_by_role("button", name="Sair")).to_be_visible()
    admin.reload()
    expect(admin.get_by_role("heading", name=re.compile(r"Membros \("))).to_be_visible()
    expect(admin.locator(".member-list").first).not_to_contain_text(INVITED)
