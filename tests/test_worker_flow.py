from io import BytesIO

from fastapi.testclient import TestClient

from tts_service.main import create_app
from tts_service.providers.base import SynthesisRequest, SynthesisResult, TTSProvider
from tts_service.services.worker import WorkerService


class RecordingProvider(TTSProvider):
    def __init__(self) -> None:
        self.requests: list[SynthesisRequest] = []

    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        self.requests.append(request)
        return SynthesisResult(audio_bytes=b"RIFFrecorded", sample_rate=24000, format="wav")


class FailingProvider(TTSProvider):
    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        raise RuntimeError("model path is invalid")


def test_worker_uses_default_voice_when_job_has_only_text(tmp_path) -> None:
    app = create_app(
        {
            "database_url": f"sqlite:///{tmp_path}/app.db",
            "storage_root": str(tmp_path / "storage"),
        }
    )
    app.state.provider = RecordingProvider()
    client = TestClient(app)

    bootstrap = client.post("/debug/bootstrap-user", json={"name": "alice"})
    api_key = bootstrap.json()["api_key"]
    job = client.post(
        "/v1/jobs",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"text": "hello"},
    ).json()

    worker = WorkerService(
        session_factory=app.state.session_factory,
        file_storage=app.state.file_storage,
        provider=app.state.provider,
        job_service=app.state.job_service,
    )

    worker.process_next_job()

    request = app.state.provider.requests[0]
    assert request.job_id == job["id"]
    assert request.request_mode == "base_tts"
    assert request.reference_audio_path is None
    assert request.reference_text is None


def test_worker_uses_saved_voice_reference_audio_and_text(tmp_path) -> None:
    app = create_app(
        {
            "database_url": f"sqlite:///{tmp_path}/app.db",
            "storage_root": str(tmp_path / "storage"),
        }
    )
    app.state.provider = RecordingProvider()
    client = TestClient(app)

    bootstrap = client.post("/debug/bootstrap-user", json={"name": "alice"})
    api_key = bootstrap.json()["api_key"]
    voice = client.post(
        "/v1/voices",
        headers={"Authorization": f"Bearer {api_key}"},
        files={"reference_audio": ("reference.wav", BytesIO(b"RIFFdemo"), "audio/wav")},
        data={
            "name": "alice-voice",
            "clone_mode": "ultimate_clone",
            "consent_statement": "owned by user",
            "reference_text": "hello reference",
        },
    ).json()
    client.post(
        "/v1/jobs",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"text": "hello world", "voice_profile_id": voice["id"]},
    )

    worker = WorkerService(
        session_factory=app.state.session_factory,
        file_storage=app.state.file_storage,
        provider=app.state.provider,
        job_service=app.state.job_service,
    )

    worker.process_next_job()

    request = app.state.provider.requests[0]
    assert request.request_mode == "ultimate_clone"
    assert request.reference_audio_path is not None
    assert request.reference_audio_path.endswith("reference.wav")
    assert request.reference_text == "hello reference"


def test_worker_claims_and_completes_queued_job(tmp_path) -> None:
    app = create_app(
        {
            "database_url": f"sqlite:///{tmp_path}/app.db",
            "storage_root": str(tmp_path / "storage"),
        }
    )
    client = TestClient(app)

    bootstrap = client.post("/debug/bootstrap-user", json={"name": "alice"})
    api_key = bootstrap.json()["api_key"]
    voice = client.post(
        "/v1/voices",
        headers={"Authorization": f"Bearer {api_key}"},
        files={"reference_audio": ("reference.wav", BytesIO(b"RIFFdemo"), "audio/wav")},
        data={
            "name": "alice-voice",
            "clone_mode": "clone",
            "consent_statement": "owned by user",
        },
    ).json()
    job = client.post(
        "/v1/jobs",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"text": "hello", "voice_profile_id": voice["id"]},
    ).json()

    worker = WorkerService(
        session_factory=app.state.session_factory,
        file_storage=app.state.file_storage,
        provider=app.state.provider,
        job_service=app.state.job_service,
    )

    processed = worker.process_next_job()

    assert processed is True

    detail = client.get(f"/v1/jobs/{job['id']}", headers={"Authorization": f"Bearer {api_key}"})
    assert detail.status_code == 200
    assert detail.json()["status"] == "succeeded"
    assert detail.json()["audio_url"].endswith("/audio")


def test_worker_marks_job_failed_when_provider_raises(tmp_path) -> None:
    app = create_app(
        {
            "database_url": f"sqlite:///{tmp_path}/app.db",
            "storage_root": str(tmp_path / "storage"),
        }
    )
    app.state.provider = FailingProvider()
    client = TestClient(app)

    bootstrap = client.post("/debug/bootstrap-user", json={"name": "alice"})
    api_key = bootstrap.json()["api_key"]
    job = client.post(
        "/v1/jobs",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"text": "hello"},
    ).json()

    worker = WorkerService(
        session_factory=app.state.session_factory,
        file_storage=app.state.file_storage,
        provider=app.state.provider,
        job_service=app.state.job_service,
    )

    processed = worker.process_next_job()

    assert processed is True

    detail = client.get(f"/v1/jobs/{job['id']}", headers={"Authorization": f"Bearer {api_key}"})
    assert detail.status_code == 200
    assert detail.json()["status"] == "failed"
    assert detail.json()["error_code"] == "synthesis_failed"
    assert detail.json()["error_message"] == "model path is invalid"
    assert detail.json()["audio_url"] is None
