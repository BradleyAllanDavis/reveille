"""Live-source credential resolution: env var directly, or via a command
env var (the ``op-read-serialized``-style indirection), or fail loud."""

import pytest

from reveille.cli import _env_flag, _resolve_secret


def test_resolve_secret_prefers_direct_env(monkeypatch):
    monkeypatch.setenv("HA_TOKEN", "direct-value")
    monkeypatch.delenv("HA_TOKEN_CMD", raising=False)
    assert _resolve_secret("HA_TOKEN", "HA_TOKEN_CMD") == "direct-value"


def test_resolve_secret_runs_command_when_no_direct_value(monkeypatch):
    monkeypatch.delenv("HA_TOKEN", raising=False)
    monkeypatch.setenv("HA_TOKEN_CMD", "echo from-command")
    assert _resolve_secret("HA_TOKEN", "HA_TOKEN_CMD") == "from-command"


def test_resolve_secret_fails_loud_when_neither_set(monkeypatch):
    monkeypatch.delenv("HA_TOKEN", raising=False)
    monkeypatch.delenv("HA_TOKEN_CMD", raising=False)
    with pytest.raises(SystemExit):
        _resolve_secret("HA_TOKEN", "HA_TOKEN_CMD")


def test_env_flag_defaults_true_and_parses_falsy_strings(monkeypatch):
    monkeypatch.delenv("HA_VERIFY_SSL", raising=False)
    assert _env_flag("HA_VERIFY_SSL") is True
    monkeypatch.setenv("HA_VERIFY_SSL", "false")
    assert _env_flag("HA_VERIFY_SSL") is False
    monkeypatch.setenv("HA_VERIFY_SSL", "0")
    assert _env_flag("HA_VERIFY_SSL") is False
