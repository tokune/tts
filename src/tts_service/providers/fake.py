from tts_service.providers.base import SynthesisRequest, SynthesisResult, TTSProvider


class FakeTTSProvider(TTSProvider):
    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        payload = f"FAKE:{request.job_id}:{request.text}".encode("utf-8")
        return SynthesisResult(audio_bytes=b"RIFF" + payload, sample_rate=24000, format="wav")
