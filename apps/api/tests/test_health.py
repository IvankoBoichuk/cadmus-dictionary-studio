import socket

import pytest
from cadmus.config import Settings
from cadmus_api.main import create_app
from fastapi.testclient import TestClient


def test_health_returns_exact_stable_response() -> None:
    settings = Settings(name="cadmus-api", version="1.2.3")

    with TestClient(create_app(settings)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "cadmus-api",
        "version": "1.2.3",
    }


def test_health_does_not_open_external_connections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_connection(*args: object, **kwargs: object) -> None:
        raise AssertionError("health must not open an external connection")

    monkeypatch.setattr(socket.socket, "connect", reject_connection)

    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
