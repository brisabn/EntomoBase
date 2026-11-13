import os
import re

FRONTEND = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend")


def read(name):
    with open(os.path.join(FRONTEND, name), encoding="utf-8") as f:
        return f.read()


def dictionary():
    source = read("i18n.js")
    messages = source[source.index("const MESSAGES"):source.index("const VOCABULARY")]
    portuguese, english = messages.split("\n  en: {", 1)
    key = re.compile(r"'([a-zA-Z_]+\.[a-zA-Z_0-9]+)':")
    return set(key.findall(portuguese)), set(key.findall(english))


def test_every_portuguese_text_has_an_english_translation():
    portuguese, english = dictionary()
    assert portuguese - english == set(), "missing in English"


def test_there_are_no_english_texts_without_a_portuguese_one():
    portuguese, english = dictionary()
    assert english - portuguese == set(), "missing in Portuguese"


def test_every_text_used_by_the_site_exists_in_the_dictionary():
    portuguese, _ = dictionary()
    used = set()
    for name in ("index.html", "app.js"):
        source = read(name)
        used |= set(re.findall(r"\bt\('([\w.]+)'", source))
        used |= set(re.findall(r"\$root\.t\('([\w.]+)'", source))
        used |= set(re.findall(r"\bt\(\\'([\w.]+)\\'", source))
        used |= set(re.findall(r"""\bt\(`([\w.]+)`""", source))
    dynamic_prefixes = {"tab.", "sort.", "filter.", "count.", "importField.", "warning.", "error.", "problem.", "field."}
    missing = {k for k in used if k not in portuguese and not any(k.startswith(p) and k.endswith(".") for p in dynamic_prefixes)}
    assert missing == set()


def test_dynamic_text_keys_exist():
    portuguese, _ = dictionary()
    expected = set()
    expected |= {f"tab.{x}" for x in ("about", "projects", "collection")}
    expected |= {f"sort.{x}" for x in ("recent", "title", "species")}
    expected |= {f"filter.{x}" for x in ("year", "group", "status", "locality")}
    expected |= {f"warning.{x}" for x in ("fuzzy", "synonym", "genus_only", "not_found")}
    # projects show who can see them: a badge and a hint for each visibility
    expected |= {f"badge.{x}" for x in ("private", "unlisted", "public")}
    expected |= {f"visibility.hint_{x}" for x in ("private", "unlisted", "public")}
    # the three points of the home page, and the role shown next to each of the person's laboratories
    expected |= {f"home.{x}_{part}" for x in ("specimens", "open", "private") for part in ("title", "text")}
    expected |= {f"role.{x}" for x in ("admin", "researcher")}
    source = read("app.js")
    fields = re.search(r"const IMPORT_FIELDS = \[(.*?)\];", source, re.S).group(1)
    expected |= {f"importField.{f}" for f in re.findall(r"'(\w+)'", fields)}
    assert expected - portuguese == set()


# every backend module except the tests, since error codes are raised from several of them
def backend_source(backend):
    parts = []
    for name in sorted(os.listdir(backend)):
        if name.endswith(".py"):
            with open(os.path.join(backend, name), encoding="utf-8") as f:
                parts.append(f.read())
    return "\n".join(parts)


def test_every_api_error_code_has_a_text():
    portuguese, _ = dictionary()
    backend = os.path.join(os.path.dirname(FRONTEND), "backend")
    codes = set(re.findall(r'api_error\(\d+, "(\w+)"', backend_source(backend)))
    assert codes, "no error codes found"
    assert {f"error.{c}" for c in codes} - portuguese == set()


def test_every_problem_code_has_a_text():
    portuguese, _ = dictionary()
    backend = os.path.join(os.path.dirname(FRONTEND), "backend")
    with open(os.path.join(backend, "main.py"), encoding="utf-8") as f:
        source = f.read()
    codes = set(re.findall(r'Problem\(code="(\w+)"', source)) | {"required", "empty", "max", "min", "invalid_value"}
    app_js = read("app.js")
    codes |= set(re.findall(r"code: '(\w+)'", app_js))
    assert {f"problem.{c}" for c in codes} - portuguese == set()


def test_translated_vocabulary_covers_every_value_the_site_offers():
    source = read("i18n.js")
    vocabulary = source[source.index("const VOCABULARY"):source.index("// how a stored value reads")]
    for stored in ("macho", "fêmea", "indeterminado", "adulto", "operária", "soldado", "rainha", "ninfa", "larva", "pupa",
                   "no acervo", "emprestado", "em análise"):
        assert f"'{stored}'" in vocabulary or f"{stored}:" in vocabulary, stored
    seed = open(os.path.join(os.path.dirname(FRONTEND), "backend", "seed.py"), encoding="utf-8").read()
    for stored in set(re.findall(r'"(armadilha[^"]*|rede entomológica|busca ativa)"', seed)):
        assert f"'{stored}'" in vocabulary, stored
