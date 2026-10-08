from fastapi.testclient import TestClient

from app.main import app


def test_ffmpeg_status_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/ffmpeg")
        assert response.status_code == 200
        body = response.json()
        assert set(body.keys()) >= {
            "found",
            "path",
            "source",
            "on_path",
            "version",
            "winget_available",
            "upgrade_available",
        }


def test_ffmpeg_path_endpoint_rejects_bad_directory():
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/ffmpeg/path", json={"directory": "Z:/does-not-exist"})
        assert response.status_code == 500
