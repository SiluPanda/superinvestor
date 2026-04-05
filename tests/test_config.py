from __future__ import annotations

from pathlib import Path

import pytest

from superinvestor.config import CONFIG_TEMPLATE, Settings, ensure_config


class TestTomlConfig:
    def test_toml_values_loaded(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        toml_file = tmp_path / "config.toml"
        toml_file.write_text('polygon_rate_limit = 99\nfred_api_key = "toml-key"\n')

        # Clear env vars that would override TOML.
        monkeypatch.delenv("SUPERINVESTOR_POLYGON_RATE_LIMIT", raising=False)
        monkeypatch.delenv("SUPERINVESTOR_FRED_API_KEY", raising=False)

        class TestSettings(Settings):
            model_config = Settings.model_config.copy()
            model_config["toml_file"] = toml_file  # type: ignore[literal-required]

        s = TestSettings()
        assert s.polygon_rate_limit == 99
        assert s.fred_api_key == "toml-key"

    def test_env_overrides_toml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        toml_file = tmp_path / "config.toml"
        toml_file.write_text("polygon_rate_limit = 99\n")

        monkeypatch.setenv("SUPERINVESTOR_POLYGON_RATE_LIMIT", "555")

        class TestSettings(Settings):
            model_config = Settings.model_config.copy()
            model_config["toml_file"] = toml_file  # type: ignore[literal-required]

        s = TestSettings()
        assert s.polygon_rate_limit == 555


class TestEnsureConfig:
    def test_creates_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config_dir = tmp_path / "superinvestor"
        config_path = config_dir / "config.toml"
        monkeypatch.setattr("superinvestor.config.CONFIG_DIR", config_dir)
        monkeypatch.setattr("superinvestor.config.CONFIG_PATH", config_path)

        assert ensure_config() is True
        assert config_path.exists()
        assert "anthropic_api_key" in config_path.read_text()

    def test_idempotent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config_dir = tmp_path / "superinvestor"
        config_path = config_dir / "config.toml"
        monkeypatch.setattr("superinvestor.config.CONFIG_DIR", config_dir)
        monkeypatch.setattr("superinvestor.config.CONFIG_PATH", config_path)

        ensure_config()
        content = config_path.read_text()

        assert ensure_config() is False
        assert config_path.read_text() == content
