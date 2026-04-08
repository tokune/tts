from __future__ import annotations

from dataclasses import dataclass
import logging
import sys
from types import SimpleNamespace

from tts_service.providers.base import SynthesisRequest
from tts_service.providers.official_voxcpm import OfficialVoxCPMProvider


@dataclass
class FakeModel:
    sample_rate: int = 24000

    def __post_init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.tts_model = SimpleNamespace(sample_rate=self.sample_rate)

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return b"RIFFfake"


def install_fake_voxcpm(monkeypatch, model: FakeModel, calls: list[dict[str, object]]) -> None:
    class FakeVoxCPM:
        @classmethod
        def from_pretrained(cls, model_path: str, **kwargs):
            calls.append({"model_path": model_path, **kwargs})
            return model

    monkeypatch.setitem(sys.modules, "voxcpm", SimpleNamespace(VoxCPM=FakeVoxCPM))


def test_official_provider_loads_voxcpm2_without_denoiser(monkeypatch, caplog) -> None:
    model = FakeModel()
    calls: list[dict[str, object]] = []
    install_fake_voxcpm(monkeypatch, model, calls)
    provider = OfficialVoxCPMProvider(model_path="openbmb/VoxCPM2", device_ids=[0])

    caplog.set_level(logging.INFO, logger="tts_service.providers.official_voxcpm")
    provider._get_model()

    assert calls == [{"model_path": "openbmb/VoxCPM2", "load_denoiser": False}]
    assert "loading VoxCPM model model_path=openbmb/VoxCPM2" in caplog.text
    assert "loaded VoxCPM model model_path=openbmb/VoxCPM2" in caplog.text


def test_official_provider_uses_reference_wav_path_for_clone(monkeypatch) -> None:
    model = FakeModel()
    calls: list[dict[str, object]] = []
    install_fake_voxcpm(monkeypatch, model, calls)
    provider = OfficialVoxCPMProvider(model_path="openbmb/VoxCPM2", device_ids=[0])

    provider.synthesize(
        SynthesisRequest(
            job_id="job-1",
            text="hello",
            voice_profile_id="voice-1",
            request_mode="clone",
            reference_audio_path="/tmp/reference.wav",
            reference_text="ignored transcript",
        )
    )

    assert model.calls == [{"text": "hello", "reference_wav_path": "/tmp/reference.wav"}]


def test_official_provider_uses_prompt_kwargs_for_ultimate_clone(monkeypatch) -> None:
    model = FakeModel()
    calls: list[dict[str, object]] = []
    install_fake_voxcpm(monkeypatch, model, calls)
    provider = OfficialVoxCPMProvider(model_path="openbmb/VoxCPM2", device_ids=[0])

    provider.synthesize(
        SynthesisRequest(
            job_id="job-1",
            text="hello",
            voice_profile_id="voice-1",
            request_mode="ultimate_clone",
            reference_audio_path="/tmp/reference.wav",
            reference_text="hello transcript",
        )
    )

    assert model.calls == [
        {
            "text": "hello",
            "reference_wav_path": "/tmp/reference.wav",
            "prompt_wav_path": "/tmp/reference.wav",
            "prompt_text": "hello transcript",
        }
    ]
