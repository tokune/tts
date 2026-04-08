from io import BytesIO

from fastapi.testclient import TestClient

from tts_service.main import create_app


def test_submit_one_off_clone_job_with_reference_audio(tmp_path) -> None:
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
        files={"reference_audio": ("prompt.wav", BytesIO(b"RIFFdemo"), "audio/wav")},
        data={
            "text": "hello world",
            "clone_mode": "ultimate_clone",
            "reference_text": "hello reference",
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["request_mode"] == "ultimate_clone"
