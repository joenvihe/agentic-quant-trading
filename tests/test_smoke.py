from pathlib import Path

from config.settings import Settings


def test_default_settings_are_available() -> None:
    settings = Settings()

    assert settings.project_name == "Agentic Quant Trading"
    assert settings.data_dir == Path("data")
    assert settings.research_workspace == Path("research_workspace")
    assert settings.log_level == "INFO"


def test_research_workspace_is_configurable_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("AQT_RESEARCH_WORKSPACE", "workspace-for-tests")

    assert Settings.from_env().research_workspace == Path("workspace-for-tests")
