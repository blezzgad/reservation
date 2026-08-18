import pytest

from reservation_service.core.config import Settings


def test_settings_are_loaded_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = "postgresql+asyncpg://user:password@db:5432/test_database"
    monkeypatch.setenv("RESERVATION_DATABASE_URL", database_url)
    monkeypatch.setenv("RESERVATION_APP_ENV", "test")
    monkeypatch.setenv("RESERVATION_LOG_LEVEL", "DEBUG")

    settings = Settings()

    assert settings.database_url == database_url
    assert settings.app_env == "test"
    assert settings.log_level == "DEBUG"
