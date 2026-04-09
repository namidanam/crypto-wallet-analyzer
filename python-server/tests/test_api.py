from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "python-server"}

def test_aggregates(mock_history):
    response = client.post("/aggregates", json=mock_history)
    assert response.status_code == 200
    data = response.json()
    assert data["wallet_address"] == "0x123"
    assert data["total_tx_count"] == 2
    assert data["total_volume"] == 2000.50
    assert data["unique_interacted_addresses"] == 2
    assert data["active_days"] == 2

def test_risk_score(mock_history):
    response = client.post("/risk-score", json=mock_history)
    assert response.status_code == 200
    data = response.json()
    assert data["wallet_address"] == "0x123"
    assert "overall_score" in data
    assert "risk_level" in data
