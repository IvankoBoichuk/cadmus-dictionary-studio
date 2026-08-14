from cadmus.config import Environment, Settings
from cadmus_api.main import create_app
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine


def test_application_factory_uses_typed_settings() -> None:
    settings = Settings(
        name="test-cadmus-api",
        environment=Environment.TEST,
        version="9.8.7",
    )

    app = create_app(settings)

    assert isinstance(app, FastAPI)
    assert app.title == "test-cadmus-api"
    assert app.version == "9.8.7"
    assert app.state.settings is settings
    assert app.state.settings.environment is Environment.TEST


def test_application_factory_returns_independent_instances() -> None:
    assert create_app() is not create_app()


def test_openapi_is_available_and_documents_health_contract() -> None:
    test_engine = create_engine("sqlite+pysqlite:///:memory:")
    with TestClient(create_app(database_engine=test_engine)) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    health_operation = schema["paths"]["/health"]["get"]
    response_schema = health_operation["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert response_schema == {
        "$ref": "#/components/schemas/HealthResponse",
    }
    health_schema = schema["components"]["schemas"]["HealthResponse"]
    assert health_schema["additionalProperties"] is False
    assert health_schema["required"] == ["service", "version"]
    assert set(health_schema["properties"]) == {"service", "status", "version"}
