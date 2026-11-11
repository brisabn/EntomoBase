import pytest

import main


# ---------- CORS_ORIGINS ----------
def test_origins_come_from_the_variable(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example, https://b.example/")
    assert main.load_allowed_origins() == ["https://a.example", "https://b.example"]


def test_empty_items_are_ignored(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", ",https://a.example,,")
    assert main.load_allowed_origins() == ["https://a.example"]


def test_dev_mode_allows_the_local_frontend(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS")
    monkeypatch.setenv("ENTOMOBASE_ENV", "dev")
    assert main.load_allowed_origins() == main.DEV_ORIGINS


def test_without_the_variable_and_outside_dev_nothing_is_allowed(monkeypatch, capsys):
    monkeypatch.delenv("CORS_ORIGINS")
    monkeypatch.delenv("ENTOMOBASE_ENV", raising=False)
    assert main.load_allowed_origins() == []
    assert "CORS_ORIGINS is not set" in capsys.readouterr().out


def test_the_variable_wins_over_dev_mode(monkeypatch):
    monkeypatch.setenv("ENTOMOBASE_ENV", "dev")
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example")
    assert main.load_allowed_origins() == ["https://a.example"]


# ---------- SECRET_KEY ----------
def test_the_secret_key_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "my-key")
    assert main.load_secret_key() == "my-key"


def test_without_a_secret_key_the_api_refuses_to_start(monkeypatch):
    monkeypatch.delenv("SECRET_KEY")
    monkeypatch.delenv("ENTOMOBASE_ENV", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY is not set"):
        main.load_secret_key()


def test_dev_mode_uses_a_random_key_that_changes_each_time(monkeypatch, capsys):
    monkeypatch.delenv("SECRET_KEY")
    monkeypatch.setenv("ENTOMOBASE_ENV", "dev")
    first, second = main.load_secret_key(), main.load_secret_key()
    assert first != second and len(first) >= 32
    assert "temporary key" in capsys.readouterr().out


def test_any_other_environment_name_is_not_dev(monkeypatch):
    monkeypatch.delenv("SECRET_KEY")
    monkeypatch.setenv("ENTOMOBASE_ENV", "production")
    with pytest.raises(RuntimeError):
        main.load_secret_key()
