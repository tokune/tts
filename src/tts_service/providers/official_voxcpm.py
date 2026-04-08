from __future__ import annotations

from io import BytesIO
import wave
from threading import Lock
from typing import Any

from tts_service.providers.base import SynthesisRequest, SynthesisResult, TTSProvider


class OfficialVoxCPMProvider(TTSProvider):
    def __init__(self, model_path: str, device_ids: list[int]) -> None:
        self.model_path = model_path
        self.device_ids = device_ids
        self._model: Any | None = None
        self._lock = Lock()

    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        model = self._get_model()
        kwargs: dict[str, Any] = {"text": request.text}

        if request.reference_audio_path:
            kwargs["prompt_wav_path"] = request.reference_audio_path
        if request.reference_text:
            kwargs["prompt_text"] = request.reference_text

        result = model.generate(**kwargs)
        sample_rate = getattr(getattr(model, "tts_model", None), "sample_rate", 24000)
        audio_bytes, sample_rate = self._normalize_output(result, sample_rate)
        return SynthesisResult(audio_bytes=audio_bytes, sample_rate=sample_rate, format="wav")

    def _get_model(self):
        if self._model is not None:
            return self._model

        with self._lock:
            if self._model is not None:
                return self._model
            try:
                from voxcpm import VoxCPM  # type: ignore
            except ImportError as exc:
                raise RuntimeError("voxcpm is not installed in this runtime. Install it on the GPU server.") from exc

            self._model = VoxCPM.from_pretrained(self.model_path)
            return self._model

    def _normalize_output(self, result: Any, default_sample_rate: int) -> tuple[bytes, int]:
        sample_rate = default_sample_rate
        audio = result
        if isinstance(result, tuple) and result:
            audio = result[0]
            if len(result) > 1 and isinstance(result[1], int):
                sample_rate = result[1]

        if isinstance(audio, (bytes, bytearray)):
            return bytes(audio), sample_rate
        if hasattr(audio, "read"):
            content = audio.read()
            if isinstance(content, str):
                return content.encode("utf-8"), sample_rate
            return bytes(content), sample_rate
        if hasattr(audio, "getvalue"):
            value = audio.getvalue()
            if isinstance(value, str):
                return value.encode("utf-8"), sample_rate
            return bytes(value), sample_rate
        if isinstance(audio, BytesIO):
            return audio.getvalue(), sample_rate
        if hasattr(audio, "tolist"):
            return self._encode_wave(audio.tolist(), sample_rate), sample_rate
        if isinstance(audio, list):
            return self._encode_wave(audio, sample_rate), sample_rate
        if isinstance(audio, tuple):
            return self._encode_wave(list(audio), sample_rate), sample_rate

        raise RuntimeError(f"Unsupported VoxCPM output type: {type(result)!r}")

    def _encode_wave(self, samples: list[Any], sample_rate: int) -> bytes:
        flattened = samples
        if samples and isinstance(samples[0], list):
            flattened = samples[0]

        pcm = bytearray()
        for sample in flattened:
            value = float(sample)
            value = max(-1.0, min(1.0, value))
            int_value = int(value * 32767.0)
            pcm.extend(int_value.to_bytes(2, byteorder="little", signed=True))

        buffer = BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(bytes(pcm))

        return buffer.getvalue()
