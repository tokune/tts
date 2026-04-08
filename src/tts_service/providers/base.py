from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SynthesisRequest:
    job_id: str
    text: str
    voice_profile_id: str | None
    request_mode: str = "base_tts"
    reference_audio_path: str | None = None
    reference_text: str | None = None


@dataclass(slots=True)
class SynthesisResult:
    audio_bytes: bytes
    sample_rate: int
    format: str


class TTSProvider:
    def healthcheck(self) -> bool:
        return True

    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        raise NotImplementedError
