# Types for "a list of strings" and "a value that may be None"
from typing import List, Optional
from fastapi import FastAPI
from pydantic import BaseModel, Field

# Standard tool for reading environment variables
import os
# Reads the .env file and loads its lines into environment variables
from dotenv import load_dotenv
# The library that sends requests to an AI service
from openai import OpenAI

# Load the .env file (does nothing if it's missing, e.g. on a server that sets variables itself)
load_dotenv()

# Read the three settings; os.getenv gives None if a variable isn't set
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL = os.getenv("LLM_MODEL")

# Create the AI client only if a key exists; base_url points it at Groq, timeout stops it hanging
client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL, timeout=10) if LLM_API_KEY else None

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
    # Where the message came from: "llm", "template" or "none"
    source: str


# Recommended action for each risk level
ACTIONS = {
    "High": "Back up its data and schedule replacement as soon as possible.",
    "Medium": "Schedule an inspection and keep monitoring this drive.",
}

# Instructions that tell the AI how to behave
SYSTEM_PROMPT = (
    "You write short maintenance alerts for data center technicians. "
    "Use ONLY the facts provided. Do not invent numbers, causes, dates or drive details. "
    "Write 2 or 3 plain sentences: what is wrong, then the recommended action."
)


# Build the fixed-template alert text; this is the fallback if the AI fails
def template_message(req: AlertRequest) -> str:
    # Turn the anomalies list into one readable phrase, with a default if it is empty
    issues = ", ".join(req.anomalies) if req.anomalies else "abnormal SMART readings"
    # Return the finished alert sentence
    return (
        f"{req.risk_level} risk: drive {req.drive_id} has a "
        f"{req.failure_probability:.0%} failure probability. Detected: {issues}."
    )


# Ask the AI to write the alert; returns None if anything goes wrong
def llm_message(req: AlertRequest) -> Optional[str]:
    # No client means no key was set, so skip the AI
    if client is None:
        return None
    # Wrap the call so any failure returns None instead of crashing the route
    try:
        # Build the facts the AI is allowed to use
        facts = (
            f"Drive ID: {req.drive_id}\n"
            f"Risk level: {req.risk_level}\n"
            f"Failure probability: {req.failure_probability:.0%}\n"
            f"Anomalies: {', '.join(req.anomalies) if req.anomalies else 'none listed'}\n"
            f"Recommended action: {ACTIONS[req.risk_level]}"
        )
        # Send the request to the AI service
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": facts},
            ],
            max_tokens=600,
            temperature=0.2,
        )
        # Pull the text out of the reply and trim whitespace
        text = (response.choices[0].message.content or "").strip()
        # Return the text, or None if it came back empty
        return text or None
    except Exception as exc:
        # Print the reason in the terminal so we can debug, then fall back
        print(f"LLM call failed, using template: {exc}")
        return None


# Keep the health route so the pipeline can check the service is alive
@app.get("/health")
def health():
    # Say whether a key is set, but never return the key itself
    return {"status": "ok", "llm_configured": bool(LLM_API_KEY)}


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
            source="none",
        )

    # Try the AI first; it returns None if anything goes wrong
    message = llm_message(req)
    # Remember where the text came from
    source = "llm"
    # If the AI gave nothing, fall back to the template
    if message is None:
        message = template_message(req)
        source = "template"

    # Send back the finished alert
    return AlertResponse(
        drive_id=req.drive_id,
        alert_required=True,
        severity=req.risk_level.lower(),
        message=message,
        source=source,
    )