# Lets us call our API in memory, without starting a server
from fastapi.testclient import TestClient
# Import our code so we can change its settings inside tests
import main

# Create a test client wired to our app
client = TestClient(main.app)

# A sample High-risk request that every test can reuse
HIGH_RISK = {
    "drive_id": 5,
    "failure_probability": 0.91,
    "risk_level": "High",
    "anomalies": ["High reallocated sectors", "Pending sectors detected"],
}


# Low risk drives should not produce an alert
def test_low_risk_returns_no_alert():
    # Copy the sample request and change only the risk level
    body = {**HIGH_RISK, "risk_level": "Low"}
    response = client.post("/generate-alert", json=body)
    # The request itself should succeed
    assert response.status_code == 200
    # But no alert should be raised, and no text generated
    assert response.json()["alert_required"] is False
    assert response.json()["source"] == "none"


# A probability above 1 is impossible, so it must be rejected
def test_invalid_probability_is_rejected():
    body = {**HIGH_RISK, "failure_probability": 1.7}
    response = client.post("/generate-alert", json=body)
    # 422 is FastAPI's "your data is invalid" code
    assert response.status_code == 422


# If the AI is unavailable, we must still get a template alert
def test_falls_back_to_template_when_ai_unavailable(monkeypatch):
    # Pretend no AI client exists, only for the length of this test
    monkeypatch.setattr(main, "client", None)
    response = client.post("/generate-alert", json=HIGH_RISK)
    data = response.json()
    assert response.status_code == 200
    assert data["alert_required"] is True
    # The text must come from the template, and mention the drive
    assert data["source"] == "template"
    assert "drive 5" in data["message"]