from io import BytesIO

from fastapi.testclient import TestClient

from tts_service.main import create_app


def test_list_voices_includes_system_and_user_voices(tmp_path) -> None:
    app = create_app(
        {
            "database_url": f"sqlite:///{tmp_path}/app.db",
            "storage_root": str(tmp_path / "storage"),
        }
    )
    with app.state.session_factory() as session:
        app.state.voice_service.create_system_voice(
            session=session,
            name="narrator",
            clone_mode="clone",
            reference_audio_filename="narrator.wav",
            reference_audio_content=b"RIFFsystem",
        )

    client = TestClient(app)
    bootstrap = client.post("/debug/bootstrap-user", json={"name": "alice"})
    api_key = bootstrap.json()["api_key"]
    client.post(
        "/v1/voices",
        headers={"Authorization": f"Bearer {api_key}"},
        files={"reference_audio": ("reference.wav", BytesIO(b"RIFFdemo"), "audio/wav")},
        data={
            "name": "alice-voice",
            "clone_mode": "clone",
            "consent_statement": "owned by user",
        },
    )

    listing = client.get("/v1/voices", headers={"Authorization": f"Bearer {api_key}"})

    assert listing.status_code == 200
    names = {item["name"] for item in listing.json()["items"]}
    assert names == {"narrator", "alice-voice"}
