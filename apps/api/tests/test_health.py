import socket
from collections.abc import Iterator

import pytest
from cadmus.config import Settings
from cadmus_api.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine


@pytest.fixture
def database_engine() -> Iterator[Engine]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    yield engine
    engine.dispose()


def test_health_returns_exact_stable_response(database_engine: Engine) -> None:
    settings = Settings(name="cadmus-api", version="1.2.3")

    with TestClient(create_app(settings, database_engine=database_engine)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "cadmus-api",
        "version": "1.2.3",
    }


def test_health_does_not_open_external_connections(
    monkeypatch: pytest.MonkeyPatch,
    database_engine: Engine,
) -> None:
    def reject_connection(*args: object, **kwargs: object) -> None:
        raise AssertionError("health must not open an external connection")

    with TestClient(create_app(database_engine=database_engine)) as client:
        monkeypatch.setattr(socket.socket, "connect", reject_connection)
        response = client.get("/health")

    assert response.status_code == 200
