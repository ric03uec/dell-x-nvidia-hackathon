from fastapi.testclient import TestClient

from ingestion.app import app


def test_health_returns_200_ok() -> None:
    # Arrange
    client = TestClient(app)

    # Act
    response = client.get("/health")

    # Assert
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
