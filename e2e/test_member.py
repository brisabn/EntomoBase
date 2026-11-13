# Scenario 3: a researcher of a laboratory creates a project, imports a CSV (first with a wrong row,
# which blocks the whole file), shares the project by link and opens the link without an account.
import re

from playwright.sync_api import expect

from conftest import sign_in

TITLE = "Besouros do teste de ponta a ponta"
HEADER = "Codigo Etiqueta,Ordem,Familia,Especie,Data Coleta,Local Coleta,Latitude,Longitude,Sexo\n"
GOOD = "E2E-0001,Coleoptera,Carabidae,Calosoma granulatum,2026-03-10,Campus Pampulha,-19.87,-43.96,macho\n"
WRONG = "E2E-0002,Coleoptera,Carabidae,Calosoma granulatum,2026-03-11,Campus Pampulha,norte,-43.96,fêmea\n"
FIXED = "E2E-0002,Coleoptera,Carabidae,Calosoma granulatum,2026-03-11,Campus Pampulha,-19.88,-43.96,fêmea\n"


def choose_csv(page, name, text):
    page.locator(".modal-import input[type=file]").set_input_files(
        files=[{"name": name, "mimeType": "text/csv", "buffer": text.encode("utf-8")}])


def test_a_researcher_imports_a_csv_and_shares_the_project_by_link(new_page, servers):
    page = new_page()
    page.goto(servers.site + "/#/lab/ufmg/projetos")
    sign_in(page, "pesquisa.ufmg@entomobase.test", servers.passwords["pesquisa.ufmg@entomobase.test"])
    expect(page.get_by_role("button", name="Sair")).to_be_visible()

    # a new project starts private
    page.get_by_role("button", name="Novo projeto").click()
    form = page.locator(".modal")
    form.get_by_label("Título").fill(TITLE)
    form.get_by_label("Ano").fill("2026")
    form.get_by_label("Grupo de insetos").fill("Coleoptera")
    form.get_by_role("button", name=re.compile("Salvar")).click()
    expect(page.get_by_role("heading", name=TITLE)).to_be_visible()
    expect(page.locator(".detail-cover .vis-badge")).to_have_text("Privado")

    # a file with one wrong row: the error names the row and nothing can be imported
    page.get_by_role("button", name="Importar CSV").click()
    choose_csv(page, "coleta.csv", HEADER + GOOD + WRONG)
    dialog = page.locator(".modal-import")
    expect(dialog.locator(".imp-errors")).to_contain_text("Linha 3 (E2E-0002)")
    expect(dialog.get_by_role("button", name="Importar", exact=True)).to_be_disabled()

    # the corrected file passes: two new specimens; GBIF does not answer, which only warns
    choose_csv(page, "coleta.csv", HEADER + GOOD + FIXED)
    expect(dialog.locator(".imp-counts")).to_contain_text("2 novos")
    expect(dialog.locator(".imp-errors")).to_have_count(0)
    dialog.get_by_role("button", name="Importar", exact=True).click()
    expect(page.locator(".modal-import")).to_have_count(0)
    rows = page.locator(".table tbody tr")
    expect(rows).to_have_count(2)
    expect(rows.locator("td.mono")).to_have_text(["E2E-0001", "E2E-0002"])

    # the project is still private, so a visitor cannot see it
    visitor = new_page()
    visitor.goto(servers.site + "/#/lab/ufmg/projetos")
    expect(visitor.locator(".grid .card").first).to_be_visible()
    expect(visitor.locator(".grid")).not_to_contain_text(TITLE)

    # shared by link: the page shows the link, and the link opens without an account
    page.locator(".detail-header .actions").get_by_role("button", name="Editar").click()
    page.locator(".modal select").last.select_option("unlisted")
    page.locator(".modal").get_by_role("button", name=re.compile("Salvar")).click()
    link = page.locator(".share-row input")
    expect(link).to_have_value(re.compile(re.escape(servers.site) + r"/#/compartilhado/[\w-]{20,}$"))

    stranger = new_page()
    stranger.goto(link.input_value())
    expect(stranger.get_by_role("heading", name=TITLE)).to_be_visible()
    expect(stranger.locator(".shared-note")).to_contain_text("não é público")
    expect(stranger.locator(".table tbody tr")).to_have_count(2)
    expect(stranger.get_by_role("button", name="Editar")).to_have_count(0)

    # and it is still out of the laboratory's public list
    visitor.reload()
    expect(visitor.locator(".grid .card").first).to_be_visible()
    expect(visitor.locator(".grid")).not_to_contain_text(TITLE)
