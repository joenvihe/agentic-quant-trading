from pathlib import Path

from config.settings import Settings


def test_default_settings_are_available() -> None:
    settings = Settings()

    assert settings.project_name == "Agentic Quant Trading"
    assert settings.data_dir == Path("data")
    assert settings.log_level == "INFO"
