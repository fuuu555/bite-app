from fastapi.testclient import TestClient

from api import main
from api.main import app


def test_liveness() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness_reports_database(monkeypatch) -> None:
    async def fake_check_database() -> str:
        return "3.5.3"

    monkeypatch.setattr(main, "check_database", fake_check_database)

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "ready",
        "postgis": "3.5.3",
    }


def test_readiness_returns_service_unavailable(monkeypatch) -> None:
    async def failing_check_database() -> str:
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(main, "check_database", failing_check_database)

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "detail": {"status": "not_ready", "database": "unavailable"},
    }
