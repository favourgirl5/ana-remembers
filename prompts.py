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
- Keep it short: 2-4 sentences in plain everyday language, with at most two questions.
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
Write Ana's check-in message for today. Greet the patient by first name, gently ask how
they are doing and whether they managed to take their medication. If an earlier check-in
mentioned something specific, you may follow up on it kindly.
Reply with only the message text."""


def build_summary_prompt(ctx, ana_message, patient_reply):
    """Prompt for Gemini call 2: summarize the patient's reply for the Sessions table."""
    meds = ", ".join(m["MedicationName"] for m in ctx["medications"]) or "none recorded"
    return f"""You summarize a short check-in between Ana (a companion assistant) and a patient.
The patient's medications: {meds}

Ana said: {ana_message}
Patient replied: {patient_reply}

Return ONLY valid JSON, no extra text, in this exact shape:
{{"medication_taken": true | false | null, "summary": "<1-2 neutral sentences>"}}

- medication_taken: true if they clearly took it, false if they clearly did not,
  null if the reply does not say.
- summary: factual and neutral, in third person. Always name every symptom or side effect
  mentioned and whether it is new, the same, better or worse than before (if the reply
  says). Include mood and anything worth following up next time. No judgments, no advice."""


def parse_summary_response(text):
    """Turn Gemini's JSON reply into (medication_taken, summary). Falls back safely."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned[cleaned.find("{"):]
    try:
        data = json.loads(cleaned[cleaned.find("{"): cleaned.rfind("}") + 1])
        return data.get("medication_taken"), data.get("summary", "").strip()
    except (ValueError, AttributeError):
        return None, text.strip()


if __name__ == "__main__":
    # Preview the prompt without calling Gemini.
    from db import get_patient_context
    ctx = get_patient_context(1)  # change to a PatientID that exists
    print(build_checkin_prompt(ctx))