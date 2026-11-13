# Scenario 4: the language switch translates the page and its address, and the values saved in
# Portuguese (sex, for example) are shown in English, without asking the API again for the same data.
import re

from playwright.sync_api import expect

PROJECT = "Besouros de serapilheira do Parque Estadual do Rio Doce"


def test_switching_to_english_translates_texts_addresses_and_values(new_page, servers):
    page = new_page()
    calls = []
    page.on("request", lambda r: calls.append(r.url) if r.url.startswith(servers.api) else None)
    page.goto(servers.site + "/#/lab/ufmg/projetos")
    page.locator(".grid .card").filter(has_text=PROJECT).click()
    expect(page).to_have_url(re.compile(r"#/lab/ufmg/projetos/\d+$"))
    project_id = re.search(r"/(\d+)$", page.url).group(1)
    expect(page.locator(".section-title").first).to_have_text("Espécimes")

    # in Portuguese the value is shown as it was saved
    search = page.locator(".search-table input")
    search.fill("macho")
    first = page.locator(".table tbody tr").first
    code = first.locator("td.mono").inner_text()
    first.locator("td.mono button").click()
    panel = page.locator(".panel-info")
    expect(page.locator(".panel-code")).to_have_text(code)
    expect(panel).to_contain_text("Sexo")
    expect(panel.locator("dd").filter(has_text=re.compile(r"^macho$"))).to_have_count(1)
    page.keyboard.press("Escape")
    expect(page.locator(".panel-info")).to_have_count(0)

    # the switch keeps the same project and translates its address and its texts
    before = len(calls)
    page.locator(".lang-switch").click()
    # the table search goes along in the address
    expect(page).to_have_url(re.compile(rf"#/en/lab/ufmg/projects/{project_id}\?q=macho$"))
    expect(page.locator(".section-title").first).to_have_text("Specimens")
    expect(page.get_by_role("heading", name=PROJECT)).to_be_visible()
    expect(page.locator("html")).to_have_attribute("lang", re.compile(r"^en"))
    assert page.title().startswith(PROJECT)

    # the same specimen, now with the value in English; the search understands the English word too
    search.fill("male")
    page.locator(".table tbody tr td.mono button").filter(has_text=code).click()
    expect(panel).to_contain_text("Sex")
    expect(panel.locator("dd").filter(has_text=re.compile(r"^male$"))).to_have_count(1)
    expect(panel).not_to_contain_text("macho")
    assert not [c for c in calls[before:] if "/specimens" in c], "the switch asked the API for the specimens again"
    page.keyboard.press("Escape")

    # the tabs and the address of another page are in English as well, and the switch goes back
    page.get_by_role("link", name="Projects").first.click()
    expect(page).to_have_url(re.compile(r"#/en/lab/ufmg/projects$"))
    expect(page.get_by_role("button", name="Group")).to_be_visible()
    page.locator(".lang-switch").click()
    expect(page).to_have_url(re.compile(r"#/lab/ufmg/projetos$"))
    expect(page.get_by_role("button", name="Grupo")).to_be_visible()

    # a browser set to English opens the English site from the bare address
    english = new_page(locale="en-US")
    english.goto(servers.site + "/")
    expect(english).to_have_url(re.compile(r"#/en/$"))
    expect(english.get_by_role("heading", name="Insect collections, in the open")).to_be_visible()
