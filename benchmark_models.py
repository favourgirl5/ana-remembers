"""Benchmark: free Gemini tier vs Fontys gateway (NFR1 availability, NFR5 performance).

Fair comparison: the same model (Gemini 3.7 Flash), the same prompt (Els's real check-in
prompt) and the same moment: calls alternate between the two routes.
Every call is stored in AiCalls with Source = 'benchmark' (kept out of the live figures).
Costs ROUNDS requests on the free tier and ROUNDS on the Fontys budget.

Run:  python benchmark_models.py
"""
import statistics
import time
from datetime import datetime

from db import get_login, get_patient_context, log_ai_call
from gemini_client import PORTKEY_MODEL, _ask_portkey, client, portkey
from prompts import build_checkin_prompt

ROUNDS = 10
FREE_MODEL = "gemini-3.7-flash"
PAUSE = 3  # seconds between calls, so we don't hammer either service


def call_free(prompt):
    return client.models.generate_content(model=FREE_MODEL, contents=prompt).text


def call_fontys(prompt):
    if portkey is None:
        raise RuntimeError("PORTKEY_API_KEY missing in .env")
    return _ask_portkey(prompt)


ROUTES = [("free tier", f"free/{FREE_MODEL}", call_free),
          ("Fontys gateway", f"fontys/{PORTKEY_MODEL}", call_fontys)]

els = get_login("els.test@example.com")["PatientID"]
prompt = build_checkin_prompt(get_patient_context(els))
tokens = len(prompt) // 4
print(f"Prompt: Els's check-in prompt, about {tokens} tokens. {ROUNDS} rounds.\n")

results = {name: [] for name, _, _ in ROUTES}
for i in range(1, ROUNDS + 1):
    order = ROUTES if i % 2 else ROUTES[::-1]   # alternate who goes first
    for name, label, call in order:
        start = time.time()
        try:
            call(prompt)
            ok, error = True, ""
        except Exception as e:
            ok, error = False, f"{type(e).__name__}: {e}"[:200]
        seconds = round(time.time() - start, 1)
        results[name].append((ok, seconds))
        log_ai_call(datetime.now().replace(microsecond=0), "ok" if ok else "failed", seconds,
                    label, error, tokens, source="benchmark", patient_id=els, call_type="benchmark")
        print(f"round {i:>2}  {name:<15} {'ok    ' if ok else 'FAILED'}  {seconds:>5.1f} s  {error[:60]}")
        time.sleep(PAUSE)

print("\nRoute            Success   Median   Within 10 s   Slowest")
for name, rows in results.items():
    ok_times = [s for ok, s in rows if ok]
    success = 100 * len(ok_times) / len(rows)
    median = f"{statistics.median(ok_times):.1f} s" if ok_times else "-"
    within = f"{100 * sum(1 for s in ok_times if s <= 10) / len(rows):.0f}%"
    slowest = f"{max(ok_times):.1f} s" if ok_times else "-"
    print(f"{name:<16} {success:>5.0f}%   {median:>7}   {within:>10}   {slowest:>7}")
print("\nTargets: success >= 99% (NFR1), median <= 5 s and within 10 s >= 95% (NFR5).")