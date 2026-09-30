# List is used to say "a list of strings"; BaseModel and Field describe our data
from typing import List
from fastapi import FastAPI
from pydantic import BaseModel, Field

# Create the application object
app = FastAPI(title="Drive Alert Service")


# Describe the data we expect to RECEIVE for one drive
class AlertRequest(BaseModel):
    # Which drive this prediction is about
    drive_id: int
    # Chance of failure from the prediction service, only 0 to 1 is accepted
    failure_probability: float = Field(ge=0.0, le=1.0)
    # Risk label from the prediction service: "Low", "Medium" or "High"
    risk_level: str
    # Problems found in the SMART data; empty list if none were sent
    anomalies: List[str] = []


# Describe the data we SEND BACK
class AlertResponse(BaseModel):
    drive_id: int
    alert_required: bool
    severity: str
    message: str


# Keep the health route so the pipeline can check the service is alive
@app.get("/health")
def health():
    return {"status": "ok"}


# Register a POST route, and promise FastAPI the reply matches AlertResponse
@app.post("/generate-alert", response_model=AlertResponse)
def generate_alert(req: AlertRequest):
    # Low risk drives don't need an alert, so return early with an empty message
    if req.risk_level not in ("Medium", "High"):
        return AlertResponse(
            drive_id=req.drive_id,
            alert_required=False,
            severity=req.risk_level.lower(),
            message="",
        )

    # Turn the list of anomalies into one readable phrase, with a default if empty
    issues = ", ".join(req.anomalies) if req.anomalies else "abnormal SMART readings"

    # Build the alert text from a fixed template
    message = (
        f"{req.risk_level} risk: drive {req.drive_id} has a "
        f"{req.failure_probability:.0%} failure probability. Detected: {issues}."
    )

    # Send back the finished alert
    return AlertResponse(
        drive_id=req.drive_id,
        alert_required=True,
        severity=req.risk_level.lower(),
        message=message,
    )