"""FastAPI backend for Ana Remembers.

Lets the React Native front end run check-ins. Python is still the only
orchestrator between SQL Server and Gemini; the app only talks to this API.
Every patient endpoint requires a login token, and a patient can only reach
their own data (NFR6).

Run:  python -m uvicorn api:app --reload
Docs: http://127.0.0.1:8000/docs
"""
import uuid
from datetime import date, timedelta

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import check_password, hash_password, make_token, read_token
from db import (create_patient, get_login, get_patient_context, get_session_dates,
                save_extracted_records, store_session, upsert_concerns)
from extraction import EXTRACT_PROMPT, parse_extraction
from gemini_client import get_ai_response_with_file
from escalation import higher, primary_contact, trend_escalation
from main import ask_gemini, MAX_TURNS, EXIT_WORDS
from prompts import build_checkin_prompt, build_summary_prompt, parse_summary_response

app = FastAPI(title="Ana Remembers API")

# Allow the app (Expo in the browser or on a phone) to call this API during development.
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# Check-ins that are still in progress, kept in memory while the conversation runs.
# Long-term memory (the Sessions table) is still stored in SQL Server.
CHECKINS = {}


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    full_name: str
    email: str
    password: str
    date_of_birth: str  # YYYY-MM-DD


class ConfirmRecordsRequest(BaseModel):
    diagnoses: list = []
    medications: list = []
    allergies: list = []
    care_contacts: list = []


class StartRequest(BaseModel):
    patient_id: int


class ReplyRequest(BaseModel):
    message: str


# ---------- Login ----------

def current_patient(authorization: str = Header(default="")) -> int:
    """Reads the login token from the 'Authorization: Bearer <token>' header."""
    patient_id = read_token(authorization.removeprefix("Bearer ").strip())
    if patient_id is None:
        raise HTTPException(status_code=401, detail="Please log in again.")
    return patient_id


def _only_own(patient_id: int, me: int):
    if patient_id != me:
        raise HTTPException(status_code=403, detail="You can only view your own information.")


@app.post("/auth/login")
def login(req: LoginRequest):
    user = get_login(req.email.strip())
    # Same message for unknown email and wrong password, so it doesn't reveal which emails exist.
    if user is None or not check_password(req.password, user["PasswordHash"]):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    return {
        "token": make_token(user["PatientID"]),
        "patient_id": user["PatientID"],
        "full_name": user["FullName"],
        "email": user["Email"],
    }


@app.post("/auth/register")
def register(req: RegisterRequest):
    """Create a patient account and log in straight away."""
    name = req.full_name.strip()
    email = req.email.strip().lower()
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Please enter your full name.")
    if "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Your password needs at least 8 characters.")
    try:
        dob = date.fromisoformat(req.date_of_birth.strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Please enter your date of birth as YYYY-MM-DD.")
    if get_login(email):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    patient_id = create_patient(name, email, hash_password(req.password), dob.isoformat())
    return {"token": make_token(patient_id), "patient_id": patient_id, "full_name": name, "email": email}


# ---------- Medical reports ----------

REPORT_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp"}
MAX_REPORT_BYTES = 10 * 1024 * 1024  # 10 MB


@app.post("/patients/{patient_id}/reports/extract")
def extract_report(patient_id: int, file: UploadFile = File(...), me: int = Depends(current_patient)):
    """Gemini reads the report and returns what it found. Nothing is saved yet,
    and the file itself is never stored."""
    _only_own(patient_id, me)
    if file.content_type not in REPORT_TYPES:
        raise HTTPException(status_code=400, detail="Please upload a PDF or a photo (JPG or PNG).")
    data = file.file.read()
    if len(data) > MAX_REPORT_BYTES:
        raise HTTPException(status_code=413, detail="That file is too large (max 10 MB).")
    try:
        raw = get_ai_response_with_file(EXTRACT_PROMPT, data, file.content_type)
    except Exception as e:
        print(f"[Report extraction failed: {type(e).__name__}: {e}]")
        raise HTTPException(status_code=503, detail="Ana couldn't read the report right now. Please try again later.")
    return parse_extraction(raw)


@app.post("/patients/{patient_id}/reports/confirm")
def confirm_report(patient_id: int, req: ConfirmRecordsRequest, me: int = Depends(current_patient)):
    """Save only the items the patient checked and kept."""
    _only_own(patient_id, me)
    return save_extracted_records(patient_id, req.model_dump())


# ---------- Helpers ----------

def _save_checkin(checkin_id):
    """End a check-in and store it in Sessions. Returns the SessionID or None."""
    c = CHECKINS.pop(checkin_id, None)
    if c is None:
        return None
    summary = c["summary"]
    if c["unsummarised"]:  # replies Gemini never processed (connection lost)
        raw_notes = " / ".join(c["unsummarised"])
        summary = (summary + " " if summary else "") + \
            f"[Connection lost, not summarised] Patient said: {raw_notes}"
    if not summary:
        return None

    level, reason = c.get("escalation", (None, None))
    session_id = store_session(c["patient_id"], c["medication_taken"], summary, level, reason)
    if level:
        _notify_care_team(c, level, reason)
    try:
        upsert_concerns(c["patient_id"], c.get("concerns", []))
    except Exception as e:
        print(f"[Could not update concerns: {e}]")
    return session_id


def _notify_care_team(c, level, reason):
    """Prototype 'notification': the escalation is saved with the session (care-team view)
    and shown here. A real system would send an email/SMS or page the care team."""
    name = c["ctx"]["patient"].get("FullName")
    contact = primary_contact(c["ctx"].get("care_contacts", []))
    who = "112 + " if level == "emergency" else ""
    if contact:
        who += f"{contact['Role']}: {contact['Name']} ({contact.get('Phone') or 'no phone'})"
    print(f"[ESCALATION {level.upper()}] {name}: {reason} -> notify {who}")


def _ana_turn(checkin_id, c):
    """Ask Gemini for Ana's next message about the conversation so far.
    If Gemini can't be reached, the check-in stays open so the patient can retry."""
    last_message = c["transcript"][-1][1]
    last_turn = c["turns"] >= MAX_TURNS or last_message.lower().strip(" .!") in EXIT_WORDS
    try:
        raw = ask_gemini(build_summary_prompt(c["ctx"], c["transcript"], last_turn=last_turn))
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail="Ana couldn't reach her server. Your message is safe; you can try again.",
        )

    result = parse_summary_response(raw)
    c["transcript"].append(("Ana", result["ana_reply"]))
    if result["medication_taken"] is not None:
        c["medication_taken"] = result["medication_taken"]
    if result["summary"]:
        c["summary"] = result["summary"]
    if result.get("concerns"):
        c["concerns"] = result["concerns"]
    if result.get("escalation"):  # acute red flag reported by Gemini
        acute = (result["escalation"], result.get("escalation_reason") or "Reported during check-in")
        c["escalation"] = higher(c.get("escalation", (None, None)), acute)
    c["unsummarised"].clear()

    done = last_turn or result["conversation_done"]
    session_id = _save_checkin(checkin_id) if done else None
    return {"ana_reply": result["ana_reply"], "done": done, "session_id": session_id}


def _own_checkin(checkin_id, me):
    c = CHECKINS.get(checkin_id)
    if c is None or c["patient_id"] != me:
        raise HTTPException(status_code=404, detail="Check-in not found or already ended")
    return c


# ---------- Endpoints ----------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/patients/{patient_id}")
def patient_context(patient_id: int, me: int = Depends(current_patient)):
    """What Ana knows about a patient. No Gemini call, so it costs no requests."""
    _only_own(patient_id, me)
    ctx = get_patient_context(patient_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return ctx


@app.get("/patients/{patient_id}/progress")
def progress(patient_id: int, me: int = Depends(current_patient)):
    """Streak, this week's check-ins and medications. No Gemini call."""
    _only_own(patient_id, me)
    ctx = get_patient_context(patient_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    days = {date.fromisoformat(d) for d in get_session_dates(patient_id)}
    today = date.today()

    # Streak: days in a row with a check-in, ending today (or yesterday if not checked in yet today)
    day = today if today in days else today - timedelta(days=1)
    streak = 0
    while day in days:
        streak += 1
        day -= timedelta(days=1)

    monday = today - timedelta(days=today.weekday())
    week = []
    for i in range(7):
        d = monday + timedelta(days=i)
        week.append({"date": d.isoformat(), "checked_in": d in days,
                     "is_today": d == today, "is_future": d > today})

    return {
        "streak_days": streak,
        "week": week,
        "checkins_this_week": sum(w["checked_in"] for w in week),
        "medications": ctx["medications"],
    }


@app.post("/checkins/start")
def start_checkin(req: StartRequest, me: int = Depends(current_patient)):
    """Load the patient's memory and return Ana's opening message."""
    _only_own(req.patient_id, me)
    ctx = get_patient_context(req.patient_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    try:
        ana_message = ask_gemini(build_checkin_prompt(ctx)).strip()
    except Exception:
        raise HTTPException(status_code=503, detail="Ana can't connect right now. Please try again later.")

    checkin_id = str(uuid.uuid4())
    CHECKINS[checkin_id] = {
        "patient_id": req.patient_id,
        "ctx": ctx,
        "transcript": [("Ana", ana_message)],
        "turns": 0,
        "medication_taken": None,
        "summary": "",
        "unsummarised": [],
        "concerns": [],
        # Gradual decline: Python's trend rule decides this before the conversation starts.
        "escalation": trend_escalation(ctx.get("open_concerns", [])),
    }
    return {"checkin_id": checkin_id, "ana_message": ana_message}


@app.post("/checkins/{checkin_id}/reply")
def reply(checkin_id: str, req: ReplyRequest, me: int = Depends(current_patient)):
    """Send the patient's message; get Ana's reply. Saves the session when it ends."""
    c = _own_checkin(checkin_id, me)
    if c["transcript"][-1][0] == "Patient":
        raise HTTPException(status_code=409, detail="Ana hasn't answered your last message yet. Try again first.")
    text = req.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message is empty")

    c["transcript"].append(("Patient", text))
    c["unsummarised"].append(text)
    c["turns"] += 1
    return _ana_turn(checkin_id, c)


@app.post("/checkins/{checkin_id}/retry")
def retry(checkin_id: str, me: int = Depends(current_patient)):
    """Ask Ana again about the patient's last message (after a connection problem)."""
    c = _own_checkin(checkin_id, me)
    if c["transcript"][-1][0] != "Patient":
        raise HTTPException(status_code=400, detail="There is nothing to retry.")
    return _ana_turn(checkin_id, c)


@app.post("/checkins/{checkin_id}/end")
def end_checkin(checkin_id: str, me: int = Depends(current_patient)):
    """Patient closes the chat early: save what we have. No Gemini call."""
    _own_checkin(checkin_id, me)
    return {"session_id": _save_checkin(checkin_id)}