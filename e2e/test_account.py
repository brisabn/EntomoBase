# Scenario 2: accounts. Someone creates an account, cannot sign in before confirming the e-mail,
# opens the link of the e-mail and then signs in. And an admin invites someone without an account, who
# opens the link of the invitation, creates the account there and is already in the laboratory. And someone who
# forgot the password gets a link by e-mail, chooses a new one, and later changes it on the account page. And
# someone asks for a laboratory of their own, which the platform administrator approves.
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


FORGETFUL = "pesquisa.borboletas@entomobase.test"


def test_a_forgotten_password_is_replaced_by_e_mail_and_changed_on_the_account_page(new_page, servers):
    page = new_page()
    page.goto(servers.site + "/")
    page.get_by_role("button", name="Entrar", exact=True).first.click()
    page.get_by_role("button", name="Esqueci minha senha").click()
    page.get_by_label("E-mail").fill(FORGETFUL)
    page.get_by_role("button", name="Enviar link").click()
    expect(page.get_by_role("heading", name="Confira seu e-mail")).to_be_visible()
    expect(page.locator(".modal")).to_contain_text(FORGETFUL)
    page.get_by_role("button", name="Fechar").click()
    links = servers.links_in_emails("new-password")
    assert len(links) == 1

    # the link opens the page of the new password, and its code leaves the address bar
    page.goto(links[0])
    expect(page).to_have_url(re.compile(r"#/nova-senha$"))
    page.get_by_label("Nova senha").fill("senha-nova-por-email")
    page.get_by_role("button", name="Salvar nova senha").click()
    expect(page.locator(".confirm-box")).to_contain_text("foi trocada")

    # the old password no longer works; the new one does
    page.locator(".confirm-box").get_by_role("button", name="Entrar").click()
    expect(page.get_by_label("E-mail")).to_have_value(FORGETFUL)
    page.get_by_label("Senha").fill(servers.passwords[FORGETFUL])
    page.get_by_role("button", name="Acessar").click()
    expect(page.locator(".modal .form-error")).to_contain_text("E-mail ou senha incorretos")
    page.get_by_label("Senha").fill("senha-nova-por-email")
    page.get_by_role("button", name="Acessar").click()
    expect(page.get_by_role("button", name="Sair")).to_be_visible()

    # the link works once
    other = new_page()
    other.goto(links[0])
    other.get_by_label("Nova senha").fill("mais-uma-senha-nova")
    other.get_by_role("button", name="Salvar nova senha").click()
    expect(other.locator(".confirm-box .form-error")).to_contain_text("já foi usado")

    # on the account page, through the e-mail at the top: the laboratory, and changing the password
    page.locator("a.user").click()
    expect(page.get_by_role("heading", name="Minha conta")).to_be_visible()
    expect(page.locator(".account-labs")).to_contain_text("Laboratório de Lepidoptera (demonstração)")
    page.get_by_label("Senha atual").fill("nao-e-a-senha")
    page.get_by_label("Nova senha").fill("senha-trocada-na-conta")
    page.get_by_role("button", name="Trocar a senha").click()
    expect(page.locator(".form-error")).to_contain_text("A senha atual está incorreta")
    expect(page.get_by_role("button", name="Sair")).to_be_visible()
    page.get_by_label("Senha atual").fill("senha-nova-por-email")
    page.get_by_role("button", name="Trocar a senha").click()
    expect(page.get_by_text("Senha trocada.")).to_be_visible()
    page.get_by_role("button", name="Sair").click()
    sign_in(page, FORGETFUL, "senha-trocada-na-conta")
    expect(page.get_by_role("button", name="Sair")).to_be_visible()


ASKER = "sem.laboratorio@entomobase.test"


def test_someone_asks_for_a_laboratory_and_the_platform_administrator_approves_it(new_page, servers):
    page = new_page()
    page.goto(servers.site + "/#/conta")
    sign_in(page, ASKER, servers.passwords[ASKER])
    page.get_by_role("button", name="Fazer um pedido").click()
    page.get_by_label("Nome do laboratório").fill("Coleção de Vespas")
    expect(page.get_by_label("Endereço", exact=True)).to_have_value("colecao-de-vespas")
    page.get_by_label("Endereço", exact=True).fill("vespas")
    page.get_by_label("Instituição").fill("Universidade Fictícia")
    page.get_by_label("Código da coleção").fill("VES")
    page.get_by_label("Mensagem (opcional)").fill("Cuido da coleção de vespas do departamento.")
    page.get_by_role("button", name="Enviar pedido").click()
    # the address is not from a trusted domain, so the request waits, and the form gives way to it
    expect(page.locator(".lab-request")).to_contain_text("aguarda a resposta")
    expect(page.get_by_role("button", name="Fazer um pedido")).to_have_count(0)

    admin = new_page()
    admin.goto(servers.site + "/#/plataforma")
    sign_in(admin, "super@entomobase.test", servers.passwords["super@entomobase.test"])
    row = admin.locator(".request-row").filter(has_text="Coleção de Vespas")
    expect(row).to_contain_text("Cuido da coleção de vespas do departamento.")
    expect(row).to_contain_text(ASKER)
    # approved out of the public list (the default), which keeps the numbers the other tests check
    row.get_by_role("button", name="Aprovar").click()
    expect(admin.get_by_text("Pedido aprovado: Coleção de Vespas foi criado.")).to_be_visible()
    expect(admin.locator(".lab-requests")).to_contain_text("Aprovado")

    # the person gets an e-mail with the address, and already manages the laboratory
    assert any(link.endswith("/#/lab/vespas") for link in re.findall(re.escape(servers.site) + r"/#/lab/[\w-]+",
                                                                    servers.api_log.read_text(encoding="utf-8", errors="replace")))
    page.reload()
    expect(page.locator(".lab-request")).to_contain_text("Aprovado")
    page.goto(servers.site + "/#/lab/vespas/membros")
    expect(page.get_by_role("heading", name="Convidar para o laboratório")).to_be_visible()
    visitor = new_page()
    visitor.goto(servers.site + "/#/laboratorios")
    expect(visitor.get_by_text("Laboratório de Lepidoptera (demonstração)").first).to_be_visible()
    expect(visitor.get_by_text("Coleção de Vespas")).to_have_count(0)


def test_the_platform_administrator_creates_a_laboratory_for_an_existing_account(new_page, servers):
    page = new_page()
    page.goto(servers.site + "/#/conta")
    sign_in(page, "super@entomobase.test", servers.passwords["super@entomobase.test"])
    page.get_by_role("link", name="Laboratórios da plataforma").click()
    expect(page.get_by_role("heading", name="Criar laboratório")).to_be_visible()
    # every laboratory is listed, also the one out of the public list
    expect(page.locator(".platform-labs")).to_contain_text("Grupo de Mirmecologia (demonstração)")

    # the address follows the name
    page.get_by_label("Nome", exact=True).fill("Laboratório de Abelhas Nativas")
    expect(page.get_by_label("Endereço", exact=True)).to_have_value("laboratorio-de-abelhas-nativas")
    page.get_by_label("Endereço", exact=True).fill("abelhas")
    page.get_by_label("Instituição").fill("Universidade Fictícia")
    page.get_by_label("Código da coleção").fill("ABN")
    page.get_by_label("E-mail do primeiro administrador").fill("sem.laboratorio@entomobase.test")
    page.get_by_role("button", name="Criar laboratório").click()
    expect(page.get_by_text("Laboratório Laboratório de Abelhas Nativas criado.")).to_be_visible()
    expect(page.locator(".platform-labs")).to_contain_text("sem.laboratorio@entomobase.test")

    # the person named as admin now manages it. It stays out of the public list (unticked, the default), which
    # also keeps the numbers of the home page that the other tests check
    admin = new_page()
    admin.goto(servers.site + "/#/lab/abelhas/membros")
    sign_in(admin, "sem.laboratorio@entomobase.test", servers.passwords["sem.laboratorio@entomobase.test"])
    expect(admin.get_by_role("heading", name="Convidar para o laboratório")).to_be_visible()
    visitor = new_page()
    visitor.goto(servers.site + "/#/laboratorios")
    expect(visitor.get_by_text("Laboratório de Lepidoptera (demonstração)").first).to_be_visible()
    expect(visitor.get_by_text("Laboratório de Abelhas Nativas")).to_have_count(0)
    visitor.goto(servers.site + "/#/lab/abelhas/sobre")
    expect(visitor.locator(".lab-bar")).to_contain_text("Laboratório de Abelhas Nativas")
