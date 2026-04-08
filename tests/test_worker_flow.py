from io import BytesIO

from fastapi.testclient import TestClient

from tts_service.main import create_app
from tts_service.services.worker import WorkerService


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
