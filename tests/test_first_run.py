"""Tests for first-launch factory schedule initialization."""

from app.gui.first_run import DEFAULT_SCHEDULE_NAME, ensure_user_default_schedule


def test_first_launch_copies_factory_schedule(tmp_path):
    factory = tmp_path / "factory.toml"
    factory.write_text('sound_dir = ""\n', encoding="utf-8")
    user_dir = tmp_path / "user" / "schedules"

    result = ensure_user_default_schedule(source=factory, destination_dir=user_dir)

    assert result == user_dir / DEFAULT_SCHEDULE_NAME
    assert result.read_bytes() == factory.read_bytes()


def test_existing_user_schedule_is_never_overwritten(tmp_path):
    factory = tmp_path / "factory.toml"
    factory.write_text("factory", encoding="utf-8")
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    existing = user_dir / DEFAULT_SCHEDULE_NAME
    existing.write_text("user changes", encoding="utf-8")

    result = ensure_user_default_schedule(source=factory, destination_dir=user_dir)

    assert result == existing
    assert existing.read_text(encoding="utf-8") == "user changes"


def test_missing_factory_schedule_fails_without_creating_target(tmp_path):
    user_dir = tmp_path / "user"

    try:
        ensure_user_default_schedule(
            source=tmp_path / "missing.toml",
            destination_dir=user_dir,
        )
    except FileNotFoundError as exc:
        assert "Jadwal bawaan tidak ditemukan" in str(exc)
    else:
        raise AssertionError("missing factory schedule should fail")

    assert not (user_dir / DEFAULT_SCHEDULE_NAME).exists()
