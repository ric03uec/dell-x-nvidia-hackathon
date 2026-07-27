from fastapi.testclient import TestClient

from processing.app import create_app


def test_health_endpoint_reports_ok(monkeypatch) -> None:
    monkeypatch.delenv("INGESTION_URL", raising=False)
    with TestClient(create_app()) as client:
        response = client.get("/health")

    # Assert
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "processing",
        "scorer": "disabled",
    }
