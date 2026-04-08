from io import BytesIO

from fastapi.testclient import TestClient

from tts_service.main import create_app


def test_create_and_list_user_voice_profile(tmp_path) -> None:
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
        "/v1/voices",
        headers={"Authorization": f"Bearer {api_key}"},
        files={"reference_audio": ("reference.wav", BytesIO(b"RIFFdemo"), "audio/wav")},
        data={
            "name": "alice-voice",
            "clone_mode": "clone",
            "consent_statement": "owned by user",
        },
    )

    assert response.status_code == 201
    assert response.json()["name"] == "alice-voice"

    listing = client.get("/v1/voices", headers={"Authorization": f"Bearer {api_key}"})
    assert listing.status_code == 200
    assert listing.json()["items"][0]["name"] == "alice-voice"
