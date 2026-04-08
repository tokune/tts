import pytest

from tts_service.main import create_app
from tts_service.providers.official_voxcpm import OfficialVoxCPMProvider


def test_app_uses_fake_provider_by_default(tmp_path) -> None:
    app = create_app(
        {
            "database_url": f"sqlite:///{tmp_path}/app.db",
            "storage_root": str(tmp_path / "storage"),
        }
    )

    assert app.state.provider.__class__.__name__ == "FakeTTSProvider"


def test_app_can_select_nanovllm_provider_without_loading_model(tmp_path) -> None:
    app = create_app(
        {
            "database_url": f"sqlite:///{tmp_path}/app.db",
            "storage_root": str(tmp_path / "storage"),
            "provider": "nanovllm_voxcpm",
            "voxcpm_model_path": "/srv/models/voxcpm",
        }
    )

    assert app.state.provider.__class__.__name__ == "NanoVllmVoxCpmProvider"


def test_app_can_select_official_voxcpm_provider_without_loading_model(tmp_path) -> None:
    app = create_app(
        {
            "database_url": f"sqlite:///{tmp_path}/app.db",
            "storage_root": str(tmp_path / "storage"),
            "provider": "voxcpm",
            "voxcpm_model_path": "/srv/models/voxcpm",
        }
    )

    assert app.state.provider.__class__.__name__ == "OfficialVoxCPMProvider"


def test_official_voxcpm_provider_rejects_missing_local_model_directory() -> None:
    provider = OfficialVoxCPMProvider(model_path="/srv/models/VoxCPM2-3B", device_ids=[0])

    with pytest.raises(RuntimeError, match="does not exist or is not a directory"):
        provider._get_model()
