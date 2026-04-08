from fastapi.testclient import TestClient

from tts_service.main import create_app


def test_verify_api_key_returns_user_identity(tmp_path) -> None:
    app = create_app({"database_url": f"sqlite:///{tmp_path}/app.db"})
    client = TestClient(app)

    bootstrap = client.post("/debug/bootstrap-user", json={"name": "alice"})
    assert bootstrap.status_code == 201
    api_key = bootstrap.json()["api_key"]

    response = client.post(
        "/v1/auth/keys/verify",
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "alice"
    assert response.json()["valid"] is True
