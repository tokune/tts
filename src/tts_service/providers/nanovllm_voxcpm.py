from __future__ import annotations

from tts_service.providers.base import SynthesisRequest, SynthesisResult, TTSProvider


class NanoVllmVoxCpmProvider(TTSProvider):
    def __init__(self, model_path: str, device_ids: list[int]) -> None:
        self.model_path = model_path
        self.device_ids = device_ids

    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        try:
            import nanovllm_voxcpm  # type: ignore  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "nanovllm_voxcpm is not installed in this runtime. Install it on the GPU server only."
            ) from exc

        raise NotImplementedError(
            "Production Nano-vLLM VoxCPM inference wiring must run on the server runtime with the model installed."
        )
