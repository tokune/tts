from tts_service import config


def test_build_settings_loads_values_from_root_dotenv(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("TTS_SERVICE_PROVIDER=voxcpm\n", encoding="utf-8")

    monkeypatch.setattr(config, "ROOT_ENV_FILE", env_file)
    monkeypatch.delenv("TTS_SERVICE_PROVIDER", raising=False)

    settings = config.build_settings()

    assert settings.provider == "voxcpm"


def test_build_settings_prefers_process_environment_over_root_dotenv(
    tmp_path, monkeypatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("TTS_SERVICE_PROVIDER=fake\n", encoding="utf-8")

    monkeypatch.setattr(config, "ROOT_ENV_FILE", env_file)
    monkeypatch.setenv("TTS_SERVICE_PROVIDER", "voxcpm")

    settings = config.build_settings()

    assert settings.provider == "voxcpm"


def test_build_settings_prefers_explicit_overrides_over_env_sources(
    tmp_path, monkeypatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("TTS_SERVICE_PROVIDER=fake\n", encoding="utf-8")

    monkeypatch.setattr(config, "ROOT_ENV_FILE", env_file)
    monkeypatch.setenv("TTS_SERVICE_PROVIDER", "voxcpm")

    settings = config.build_settings({"provider": "nanovllm_voxcpm"})

    assert settings.provider == "nanovllm_voxcpm"
