"""Prompt templates for Ana Remembers.
 
Two prompts per check-in:
  1. build_checkin_prompt   -> Ana's opening message to the patient
  2. build_summary_prompt   -> turns the patient's reply into a short record for Sessions
"""
import json
 
ANA_PERSONA = """You are Ana, a warm and calm check-in companion for a patient living with heart failure.
Rules:
- Stay positive, steady and kind no matter how the patient responds. Do not mirror
  frustration, sadness or rudeness; stay calm and supportive.
- Be non-judgmental and never pressure the patient. A missed dose is fine to talk about.
- Keep it short: 1-3 sentences in plain everyday language. Ask exactly ONE question per
  message and wait for the answer; save other questions for the next message.
- Base your questions on the patient's records and earlier check-ins: their diagnoses,
  medications and anything they mentioned before (symptoms, side effects, mood).
  Mention past details naturally, without listing them.
- Symptoms: if the patient reports a NEW symptom, or a known symptom that is WORSE than in
  earlier check-ins, gently encourage them to contact their doctor. If it sounds severe
  (chest pain, severe breathlessness at rest, fainting), tell them to call their local
  emergency number. A known symptom that is stable needs no referral.
- You do not give medical advice, change doses or diagnose.
- Never invent facts that are not in the context below."""
 
 
def _first_name(full_name):
    return (full_name or "").split()[0] if full_name else "there"
 
 
def _format_list(items, fields, empty="None recorded."):
    if not items:
        return empty
    lines = []
    for item in items:
        parts = [str(item.get(f)) for f in fields if item.get(f) not in (None, "")]
        lines.append("- " + " | ".join(parts))
    return "\n".join(lines)
 
 
def _format_context(ctx):
    p = ctx["patient"]
    return f"""PATIENT
Name: {_first_name(p.get("FullName"))}
Allergies: {p.get("Allergies") or "None recorded"}
 
DIAGNOSES (name | date | presenting symptoms)
{_format_list(ctx["diagnoses"], ["DiagnosisName", "DiagnosisDate", "PresentingSymptoms"])}
 
MEDICATIONS (name | dosage | frequency | start date)
{_format_list(ctx["medications"], ["MedicationName", "Dosage", "Frequency", "StartDate"])}
 
RECENT CHECK-INS, newest first (date | medication taken | summary)
{_format_list(ctx["recent_sessions"], ["SessionDate", "MedicationTaken", "ConversationSummary"],
              empty="No earlier check-ins. This is the first one.")}"""
 
 
def build_checkin_prompt(ctx):
    """Prompt for Gemini call 1: Ana's check-in message."""
    return f"""{ANA_PERSONA}
 
{_format_context(ctx)}
 
TASK
Write Ana's opening message for today. Greet the patient by first name and ask ONE
question: how they are doing today. Medication, symptoms and anything from earlier
check-ins will come up in the next messages, one at a time.
Reply with only the message text."""
 
 
def _format_transcript(transcript):
    return "\n".join(f"{speaker}: {text}" for speaker, text in transcript)


def build_summary_prompt(ctx, transcript, last_turn=False):
    """Prompt for each patient reply: Ana's next message + a running summary for Sessions.

    transcript: list of (speaker, text) tuples, e.g. [("Ana", "..."), ("Patient", "...")]
    """
    ending = (
        "This is the LAST message of today's check-in: thank the patient warmly and say goodbye."
        if last_turn else
        "If Ana still has a relevant follow-up (from the records, earlier check-ins or what the "
        "patient just said), ask it. If everything is covered, close warmly and set "
        "conversation_done to true."
    )
    return f"""{ANA_PERSONA}

{_format_context(ctx)}

TODAY'S CHECK-IN SO FAR
{_format_transcript(transcript)}

TASK
Write Ana's next message. {ending}
Return ONLY valid JSON, no extra text, in this exact shape:
{{"ana_reply": "<Ana's next message>", "conversation_done": true | false, "medication_taken": true | false | null, "summary": "<1-3 neutral sentences>"}}

- ana_reply: follows all the rules above (including the symptom rules).
- conversation_done: true when Ana is saying goodbye, otherwise false.
- medication_taken: true if they clearly took it today, false if they clearly did not,
  null if not said yet.
- summary: covers the WHOLE check-in so far, factual and neutral, in third person. Always
  name every symptom or side effect mentioned and whether it is new, the same, better or
  worse than before (if said). Include mood and anything worth following up next time.
  No judgments, no advice."""


def parse_summary_response(text):
    """Turn Gemini's JSON into a dict. Falls back safely if the JSON is broken."""
    cleaned = text.strip()
    try:
        data = json.loads(cleaned[cleaned.find("{"): cleaned.rfind("}") + 1])
        return {
            "ana_reply": str(data.get("ana_reply", "")).strip(),
            "conversation_done": bool(data.get("conversation_done", False)),
            "medication_taken": data.get("medication_taken"),
            "summary": str(data.get("summary", "")).strip(),
        }
    except (ValueError, AttributeError):
        return {
            "ana_reply": "Thank you for checking in with me today. Take care!",
            "conversation_done": True,
            "medication_taken": None,
            "summary": cleaned,
        }