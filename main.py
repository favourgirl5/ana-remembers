"""Run one Ana Remembers check-in in the terminal."""
import time
import json
 
from db import get_patient_context, store_session
from gemini_client import get_ai_response
from prompts import build_checkin_prompt, build_summary_prompt, parse_summary_response
 
PATIENT_ID = 1  # change to a PatientID that exists
 
 
def ask_gemini(prompt, attempts=2):
    """Call Gemini, waiting and retrying if the model is busy (e.g. 503 errors)."""
    for attempt in range(1, attempts + 1):
        try:
            return get_ai_response(prompt)
        except Exception as e:
            if attempt == attempts or "429" in str(e):   # quota used up: retrying won't help
                raise
            wait = 2 ** attempt  # 2, 4, 8 seconds
            print(f"[Gemini busy ({type(e).__name__}), retrying in {wait}s...]")
            time.sleep(wait)
 
 
MAX_TURNS = 5                      # patient replies per check-in
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
    unsummarised = []

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
        unsummarised.clear()

        if last_turn or result["conversation_done"]:
            break

    # 4. Save the session once, so Ana remembers next time
    if not summary:
        print("Nothing to save from this check-in.")
        return
    try:
       session_id = store_session(patient_id, medication_taken, summary)
       print(f"[Saved session {session_id}] medication_taken={medication_taken}")
       print(f"[Summary] {summary}")
    except Exception as e:
       backup = {"patient_id": patient_id, "medication_taken": medication_taken,
                "summary": summary, "time": time.strftime("%Y-%m-%d %H:%M:%S")}
       with open("unsaved_sessions.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(backup) + "\n")
       print(f"[Database unavailable: session kept in unsaved_sessions.jsonl] {str(e)[:80]}")
      

if __name__ == "__main__":
    import sys
    patient_id = int(sys.argv[1]) if len(sys.argv) > 1 else PATIENT_ID
    run_checkin(patient_id)