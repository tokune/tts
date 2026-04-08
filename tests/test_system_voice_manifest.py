import json

from fastapi.testclient import TestClient

from tts_service.main import create_app
from tts_service.providers.base import SynthesisRequest, SynthesisResult, TTSProvider
from tts_service.services.worker import WorkerService


class RecordingProvider(TTSProvider):
    def __init__(self) -> None:
        self.requests: list[SynthesisRequest] = []

    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        self.requests.append(request)
        return SynthesisResult(audio_bytes=b"RIFFsystem", sample_rate=24000, format="wav")


def test_app_loads_system_voices_from_manifest_and_uses_them_for_jobs(tmp_path) -> None:
    manifest_path = tmp_path / "system_voices.json"
    reference_path = tmp_path / "narrator.wav"
    reference_path.write_bytes(b"RIFFnarrator")
    manifest_path.write_text(
        json.dumps(
            [
                {
                    "name": "narrator",
                    "clone_mode": "clone",
                    "audio_path": str(reference_path),
                    "source_label": "builtin:narrator",
                }
            ]
        ),
        encoding="utf-8",
    )

    app = create_app(
        {
            "database_url": f"sqlite:///{tmp_path}/app.db",
            "storage_root": str(tmp_path / "storage"),
            "system_voices_manifest_path": str(manifest_path),
        }
    )
    app.state.provider = RecordingProvider()
    client = TestClient(app)

    bootstrap = client.post("/debug/bootstrap-user", json={"name": "alice"})
    api_key = bootstrap.json()["api_key"]

    listing = client.get("/v1/voices", headers={"Authorization": f"Bearer {api_key}"})

    assert listing.status_code == 200
    body = listing.json()
    assert {item["name"] for item in body["items"]} == {"narrator"}

    voice = body["items"][0]
    job = client.post(
        "/v1/jobs",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"text": "hello narrator", "voice_profile_id": voice["id"]},
    )

    assert job.status_code == 202

    worker = WorkerService(
        session_factory=app.state.session_factory,
        file_storage=app.state.file_storage,
        provider=app.state.provider,
        job_service=app.state.job_service,
    )
    worker.process_next_job()

    request = app.state.provider.requests[0]
    assert request.voice_profile_id == voice["id"]
    assert request.reference_audio_path is not None
    assert "/uploads/voices/system/narrator/" in request.reference_audio_path
    assert request.reference_audio_path.endswith("reference.wav")
