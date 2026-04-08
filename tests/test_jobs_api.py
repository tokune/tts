from io import BytesIO

from fastapi.testclient import TestClient

from tts_service.main import create_app


def test_submit_json_job_without_voice_profile_uses_base_tts(tmp_path) -> None:
    app = create_app(
        {
            "database_url": f"sqlite:///{tmp_path}/app.db",
            "storage_root": str(tmp_path / "storage"),
        }
    )
    client = TestClient(app)

    bootstrap = client.post("/debug/bootstrap-user", json={"name": "alice"})
    api_key = bootstrap.json()["api_key"]

    response = client.post(
        "/v1/jobs",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"text": "hello world"},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["request_mode"] == "base_tts"
    assert body["voice_profile_id"] is None


def test_submit_form_job_without_voice_or_reference_audio_uses_base_tts(tmp_path) -> None:
    app = create_app(
        {
            "database_url": f"sqlite:///{tmp_path}/app.db",
            "storage_root": str(tmp_path / "storage"),
        }
    )
    client = TestClient(app)

    bootstrap = client.post("/debug/bootstrap-user", json={"name": "alice"})
    api_key = bootstrap.json()["api_key"]

    response = client.post(
        "/v1/jobs",
        headers={"Authorization": f"Bearer {api_key}"},
        data={"text": "hello multipart"},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["request_mode"] == "base_tts"
    assert body["voice_profile_id"] is None


def test_submit_job_with_saved_voice_enters_queue(tmp_path) -> None:
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

    response = client.post(
        "/v1/jobs",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"text": "hello world", "voice_profile_id": voice["id"]},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["voice_profile_id"] == voice["id"]
