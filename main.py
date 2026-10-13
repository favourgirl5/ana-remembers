"""Run one Ana Remembers check-in in the terminal."""
from db import get_patient_context, store_session
from gemini_client import get_ai_response
from prompts import build_checkin_prompt, build_summary_prompt, parse_summary_response

PATIENT_ID = 1  # change to a PatientID that exists


def run_checkin(patient_id):
    # 1. Memory: load everything Ana knows from SQL Server
    ctx = get_patient_context(patient_id)
    if ctx is None:
        print(f"No patient found with ID {patient_id}.")
        return

    # 2. Gemini call 1: Ana's check-in message
    ana_message = get_ai_response(build_checkin_prompt(ctx)).strip()
    print(f"\nAna: {ana_message}\n")

    # 3. Patient answers
    patient_reply = input("You: ").strip()
    if not patient_reply:
        print("No reply given, nothing saved.")
        return

    # 4. Gemini call 2: Ana's reply + summary
    raw = get_ai_response(build_summary_prompt(ctx, ana_message, patient_reply))
    ana_reply, medication_taken, summary = parse_summary_response(raw)
    print(f"\nAna: {ana_reply}\n")

    # 5. Save the session so Ana remembers next time
    session_id = store_session(patient_id, medication_taken, summary)
    print(f"[Saved session {session_id}] medication_taken={medication_taken}")
    print(f"[Summary] {summary}")


if __name__ == "__main__":
    run_checkin(PATIENT_ID)