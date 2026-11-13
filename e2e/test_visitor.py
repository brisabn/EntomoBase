# Scenario 1: a visitor, without an account, goes from the home page to a specimen of a laboratory
# and never sees a private project, a link-only project or an internal field.
import re

from playwright.sync_api import expect


def test_a_visitor_browses_from_the_home_page_to_a_specimen(page, servers):
    # every answer of the API that reaches the browser, to check what the screen does not show
    answers = []
    page.on("response", lambda r: answers.append(r) if r.url.startswith(servers.api) and r.ok else None)
    page.goto(servers.site + "/")
    expect(page.get_by_role("heading", name="Coleções de insetos, abertas")).to_be_visible()

    # the numbers and the cards count the two listed laboratories only; formigas is left out of the list
    page.locator(".home-stat").first.wait_for()
    stats = dict(page.locator(".home-stat").evaluate_all(
        "s => s.map(x => [x.querySelector('dt').textContent.trim(), x.querySelector('dd').textContent.trim()])"))
    assert stats["laboratórios"] == "2" and stats["projetos públicos"] == "6"
    cards = page.locator(".grid .card")
    expect(cards).to_have_count(2)
    expect(page.locator(".grid")).not_to_contain_text("Mirmecologia")

    # the map shows points of both laboratories
    expect(page.locator(".home-map .leaflet-marker-icon, .home-map .marker-cluster").first).to_be_visible()
    expect(page.locator(".home-map .legend")).to_contain_text("Laboratório de Lepidoptera")

    # the card opens the laboratory, which lists its public projects only
    cards.filter(has_text="EntomoBase UFMG").click()
    expect(page).to_have_url(re.compile(r"#/lab/ufmg/projetos$"))
    titles = page.locator(".grid .card-title")
    expect(titles).to_have_count(5)
    expect(page.locator(".grid")).not_to_contain_text("Joaninhas urbanas")  # private
    expect(page.locator(".grid")).not_to_contain_text("Polinizadores da Chapada")  # only with the link
    expect(page.locator(".vis-badge")).to_have_count(0)

    # the group filter leaves the one butterfly project
    page.get_by_role("button", name="Grupo").click()
    page.get_by_role("option", name="Lepidoptera").click()
    expect(titles).to_have_text(["Borboletas frugívoras do Itacolomi"])
    page.get_by_role("button", name="Limpar filtros").first.click()
    expect(titles).to_have_count(5)

    # the project page and the panel of one specimen
    page.get_by_role("button", name="Grupo").click()
    page.get_by_role("option", name="Lepidoptera").click()
    titles.first.click()
    expect(page.get_by_role("heading", name="Borboletas frugívoras do Itacolomi")).to_be_visible()
    rows = page.locator(".table tbody tr")
    expect(rows.first).to_contain_text("ITA-")
    code = rows.first.locator("td.mono").inner_text()
    rows.first.locator("td.mono button").click()
    expect(page.locator(".panel-code")).to_have_text(code)
    expect(page.locator(".panel-title")).not_to_be_empty()

    # nothing internal reaches a visitor: no section and no edit button on the screen, and not even
    # in what the browser received, where the screen could hide it (the seed fills every internal field)
    expect(page.locator(".panel-internal")).to_have_count(0)
    expect(page.get_by_role("button", name="Editar")).to_have_count(0)
    received = [r.text() for r in answers if "json" in (r.headers.get("content-type") or "")]
    assert any("ITA-" in body for body in received), "the specimens of the project were not received"
    for field in ("collector", "field_number", "storage_location", "internal_notes"):
        assert not any(f'"{field}"' in body for body in received), f"{field} reached the browser of a visitor"
