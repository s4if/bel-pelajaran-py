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


def test_packaged_resource_directory_from_environment(monkeypatch, tmp_path):
    resources = tmp_path / "usr" / "share" / paths.APP_NAME
    monkeypatch.setenv(paths.RESOURCE_DIR_ENV, str(resources))

    assert paths.app_root() == resources
    assert paths.assets_dir() == resources / "assets"
    assert paths.configs_dir() == resources / "configs"
    assert paths.is_bundled_resource(resources / "configs" / "konfig.toml")
    assert not paths.is_bundled_resource(tmp_path / "user" / "konfig.toml")


def test_relative_resource_directory_is_ignored(monkeypatch):
    monkeypatch.setenv(paths.RESOURCE_DIR_ENV, "relative/resources")

    assert paths.app_root() == Path(paths.__file__).resolve().parent.parent


def test_relative_xdg_home_uses_default(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", "relative-config")

    assert paths.config_dir() == Path.home() / ".config" / paths.APP_NAME
