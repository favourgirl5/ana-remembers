"""Run one Ana Remembers check-in in the terminal."""
import json
import time

from db import get_patient_context, store_session, upsert_concerns
from escalation import higher, primary_contact, trend_escalation
from gemini_client import get_ai_response
from prompts import build_checkin_prompt, build_summary_prompt, parse_summary_response
 
PATIENT_ID = 1  # change to a PatientID that exists
 
 
def ask_gemini(prompt, attempts=2, patient_id=None, call_type=None):
    """Call Gemini, waiting and retrying if the model is busy (e.g. 503 errors).
    Every call is logged for the monitoring report."""
    start = time.time()
    for attempt in range(1, attempts + 1):
        try:
            text = get_ai_response(prompt)
            _log_call(start, "ok", "", prompt, patient_id, call_type)
            return text
        except Exception as e:
            if attempt == attempts or "429" in str(e):   # quota used up: retrying won't help
                _log_call(start, "failed", str(e)[:60], prompt, patient_id, call_type)
            wait = 2 ** attempt
            print(f"[Gemini busy ({type(e).__name__}), retrying in {wait}s...]")
            time.sleep(wait)


def _log_call(start, result, error, prompt="", patient_id=None, call_type=None):
    import csv, datetime, gemini_client
    from db import log_ai_call
    now = datetime.datetime.now().replace(microsecond=0)
    seconds = round(time.time() - start, 1)
    model = getattr(gemini_client, "last_model_used", "") if result == "ok" else ""
    tokens = len(prompt) // 4   # estimate: 1 token is about 4 characters
    try:
        log_ai_call(now, result, seconds, model, error, tokens, patient_id=patient_id, call_type=call_type)
    except Exception:  # database unreachable: keep the call in the CSV instead
        with open("gemini_log.csv", "a", newline="") as f:
            csv.writer(f).writerow([now.isoformat(), result, seconds, model, error, tokens])
 
MAX_TURNS = 15                     # patient replies per check-in
EXIT_WORDS = {"bye", "goodbye", "exit", "quit", "stop"}


def run_checkin(patient_id):
    # 1. Memory: load everything Ana knows from SQL Server
    ctx = get_patient_context(patient_id)
    if ctx is None:
        print(f"No patient found with ID {patient_id}.")
        return

    # 2. Ana opens the check-in
    try:
        ana_message = ask_gemini(build_checkin_prompt(ctx)).strip()
    except Exception as e:
        print("\nAna: Sorry, I can't connect right now. Please try again a little later.")
        print(f"[Debug] {str(e)[:120]}")
        return
    print(f"\nAna: {ana_message}\n")
    transcript = [("Ana", ana_message)]

    medication_taken = None
    summary = ""
    concerns = []
    unsummarised = []
    # Gradual decline: Python's trend rule decides this before the conversation starts.
    escalation = trend_escalation(ctx.get("open_concerns", []))

    # 3. Conversation loop: patient replies, Ana answers, until done
    for turn in range(1, MAX_TURNS + 1):
        patient_reply = input("You: ").strip()
        if not patient_reply:
            print("(Type a reply, or 'bye' to end.)")
            patient_reply = input("You: ").strip()
            if not patient_reply:
                break
        transcript.append(("Patient", patient_reply))
        unsummarised.append(patient_reply)

        last_turn = turn == MAX_TURNS or patient_reply.lower().strip(" .!") in EXIT_WORDS
        try:
            raw = ask_gemini(build_summary_prompt(ctx, transcript, last_turn=last_turn))
        
        except Exception:
            print("\nAna: Sorry, I'm having trouble connecting right now. I've noted what you "
                  "told me, so let's talk again a little later.")
            raw_notes = " / ".join(unsummarised)
            summary = (summary + " " if summary else "") + \
                f"[Connection lost, not summarised] Patient said: {raw_notes}"
            break

        result = parse_summary_response(raw)
        print(f"\nAna: {result['ana_reply']}\n")
        transcript.append(("Ana", result["ana_reply"]))

        if result["medication_taken"] is not None:
            medication_taken = result["medication_taken"]
        if result["summary"]:
            summary = result["summary"]
        if result.get("concerns"):
            concerns = result["concerns"]
        if result.get("escalation"):  # acute red flag reported by Gemini
            acute = (result["escalation"], result.get("escalation_reason") or "Reported during check-in")
            escalation = higher(escalation, acute)
        unsummarised.clear()

        if last_turn or result["conversation_done"]:
            break

    # 4. Save the session once, so Ana remembers next time
    if not summary:
        print("Nothing to save from this check-in.")
        return
    level, reason = escalation
    try:
        session_id = store_session(patient_id, medication_taken, summary, level, reason)
        print(f"[Saved session {session_id}] medication_taken={medication_taken}")
        print(f"[Summary] {summary}")
        if level:
            contact = primary_contact(ctx.get("care_contacts", []))
            who = ("112 + " if level == "emergency" else "") + \
                (f"{contact['Role']}: {contact['Name']} ({contact.get('Phone')})" if contact else "")
            print(f"[ESCALATION {level.upper()}] {reason} -> notify {who}")
        upsert_concerns(patient_id, concerns)
        print(f"[Concerns updated] {[c.get('concern') for c in concerns]}")
    except Exception as e:
        backup = {"patient_id": patient_id, "medication_taken": medication_taken,
                  "summary": summary, "escalation": level, "escalation_reason": reason,
                  "time": time.strftime("%Y-%m-%d %H:%M:%S")}
        with open("unsaved_sessions.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(backup) + "\n")
        print(f"[Database unavailable: session kept in unsaved_sessions.jsonl] {str(e)[:80]}")


if __name__ == "__main__":
    import sys
    patient_id = int(sys.argv[1]) if len(sys.argv) > 1 else PATIENT_ID
    run_checkin(patient_id)