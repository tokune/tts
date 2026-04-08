from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TTS_SERVICE_", extra="ignore")

    app_name: str = "VoxCPM HTTP Service"
    database_url: str = "sqlite:///./storage/app.db"
    storage_root: Path = Field(default=Path("./storage"))
    system_voices_manifest_path: Path | None = None
    provider: str = "fake"
    voxcpm_model_path: str = "/srv/models/voxcpm"
    voxcpm_device_ids: list[int] = Field(default_factory=lambda: [0])
    debug_routes_enabled: bool = True


def build_settings(overrides: dict[str, Any] | None = None) -> Settings:
    data = dict(overrides or {})
    return Settings(**data)
