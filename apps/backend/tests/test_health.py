"""Health endpoint tests / 健康檢查端點測試。"""

from fastapi.testclient import TestClient

from api import main
from api.main import app


def test_liveness() -> None:
    # Liveness must remain available even when the database is unavailable.
    # 即使資料庫不可用，liveness 仍應正常回應。
    with TestClient(app) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness_reports_database(monkeypatch) -> None:
    # Mock the dependency so this unit test does not require a running database.
    # Mock 外部依賴，讓單元測試不必依賴正在運作的資料庫。
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
    # A dependency failure must be exposed as HTTP 503, not an internal 500.
    # 依賴失敗應回傳 HTTP 503，而不是未處理的 500。
    async def failing_check_database() -> str:
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(main, "check_database", failing_check_database)

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "detail": {"status": "not_ready", "database": "unavailable"},
    }
