# End-to-end tests: a real browser uses the site, which talks to a real API.
# Each run starts its own API and web server on free ports, with a fresh database filled by seed.py,
# so the tests never touch backend/entomobase.db.
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_until_up(url, process, log_path):
    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError(f"{url} stopped while starting:\n{Path(log_path).read_text(encoding='utf-8', errors='replace')}")
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except Exception:
            time.sleep(0.25)
    raise RuntimeError(f"{url} did not start in 30 seconds")


class Servers:
    def __init__(self, work):
        self.work = Path(work)
        self.api_port, self.site_port = free_port(), free_port()
        self.api = f"http://127.0.0.1:{self.api_port}"
        self.site = f"http://127.0.0.1:{self.site_port}"
        self.api_log = self.work / "api.log"
        self.passwords = {}
        self.env = {
            **os.environ,
            "ENTOMOBASE_ENV": "dev",
            "DATABASE_URL": "sqlite:///" + (self.work / "e2e.db").as_posix(),
            "SITE_URL": self.site,
            "CORS_ORIGINS": self.site,
            # the e-mails are printed in the API log, where the tests read the confirmation link
            "MAIL_BACKEND": "console",
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
            # a proxy that does not exist: GBIF never answers, so the results do not depend on it
            "HTTPS_PROXY": "http://127.0.0.1:9",
            "NO_PROXY": "127.0.0.1,localhost",
        }

    def seed(self):
        out = subprocess.run([sys.executable, "seed.py"], cwd=BACKEND, env=self.env, capture_output=True, text=True,
                             encoding="utf-8", check=True).stdout
        self.passwords = dict(re.findall(r"^\s+(\S+@entomobase\.test)\s+(\S+)", out, re.M))
        assert self.passwords, "seed.py printed no demo accounts:\n" + out

    def start(self):
        self.log = open(self.api_log, "w", encoding="utf-8")
        self.processes = [
            subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--port", str(self.api_port)], cwd=BACKEND,
                             env=self.env, stdout=self.log, stderr=subprocess.STDOUT),
            subprocess.Popen([sys.executable, "-m", "http.server", str(self.site_port), "--bind", "127.0.0.1"], cwd=FRONTEND,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
        ]
        wait_until_up(self.api + "/labs", self.processes[0], self.api_log)
        wait_until_up(self.site + "/index.html", self.processes[1], self.api_log)

    def stop(self):
        for process in self.processes:
            process.terminate()
            process.wait(timeout=10)
        self.log.close()

    def links_in_emails(self, page):
        text = self.api_log.read_text(encoding="utf-8", errors="replace")
        # an e-mail may show its link more than once; each link counts once, in the order they were sent
        return list(dict.fromkeys(re.findall(re.escape(self.site) + f"/#/{page}/" + r"[\w-]+", text)))

    def confirmation_links(self):
        return self.links_in_emails("confirm")

    def invitation_links(self):
        return self.links_in_emails("invite")


@pytest.fixture(scope="session")
def servers():
    work = tempfile.mkdtemp(prefix="entomobase_e2e_")
    s = Servers(work)
    s.seed()
    s.start()
    yield s
    s.stop()
    shutil.rmtree(work, ignore_errors=True)


def launch(playwright):
    # E2E_BROWSER picks one: chromium (downloaded with "playwright install chromium"), msedge or chrome.
    # E2E_HEADED=1 shows the window and slows each step down, to watch the tests in a presentation
    wanted = os.environ.get("E2E_BROWSER")
    choices = [wanted] if wanted else ["chromium", "msedge", "chrome"]
    headed = os.environ.get("E2E_HEADED") == "1"
    problems = []
    for name in choices:
        try:
            return playwright.chromium.launch(channel=None if name == "chromium" else name,
                                              headless=not headed, slow_mo=400 if headed else 0)
        except PlaywrightError as e:
            problems.append(f"{name}: {str(e).splitlines()[0]}")
    pytest.exit("no browser found; run 'playwright install chromium' or set E2E_BROWSER\n" + "\n".join(problems), returncode=1)


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = launch(p)
        yield b
        b.close()


@pytest.fixture
def new_page(browser, servers):
    # each page gets its own context (no shared sign-in), and the site is pointed at the API of this run
    contexts, errors = [], []

    def make(locale="pt-BR", width=1280, height=900):
        context = browser.new_context(locale=locale, viewport={"width": width, "height": height})
        context.set_default_timeout(10_000)
        # opening a page waits for Vue, Leaflet, the fonts and the images from the internet, which can be slow;
        # the checks themselves keep the 10 seconds above
        context.set_default_navigation_timeout(30_000)
        context.route("**/config.js", lambda route: route.fulfill(
            content_type="application/javascript", body=f"window.ENTOMOBASE_CONFIG = {{ apiUrl: '{servers.api}' }};"))
        page = context.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        contexts.append(context)
        return page

    yield make
    for context in contexts:
        context.close()
    assert not errors, f"JavaScript errors on the page: {errors}"


@pytest.fixture
def page(new_page):
    return new_page()


def sign_in(page, email, password):
    page.get_by_role("button", name="Entrar", exact=True).first.click()
    page.get_by_label("E-mail").fill(email)
    page.get_by_label("Senha").fill(password)
    page.get_by_role("button", name="Acessar").click()
