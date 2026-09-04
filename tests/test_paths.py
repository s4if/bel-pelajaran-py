"""Tests for platform-specific writable application directories."""

from pathlib import Path

from app import paths


def test_xdg_directories(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    assert paths.config_dir() == tmp_path / "config" / paths.APP_NAME
    assert paths.data_dir() == tmp_path / "data" / paths.APP_NAME
    assert paths.state_dir() == tmp_path / "state" / paths.APP_NAME
    assert paths.schedules_dir() == tmp_path / "config" / paths.APP_NAME / "schedules"
    assert paths.logs_dir() == tmp_path / "state" / paths.APP_NAME / "logs"


def test_windows_directories(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))

    assert paths.config_dir() == tmp_path / "roaming" / paths.APP_NAME
    assert paths.data_dir() == tmp_path / "local" / paths.APP_NAME
    assert paths.state_dir() == tmp_path / "local" / paths.APP_NAME


def test_relative_xdg_home_uses_default(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", "relative-config")

    assert paths.config_dir() == Path.home() / ".config" / paths.APP_NAME
