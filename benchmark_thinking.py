"""Benchmark: does Gemini's thinking make Ana's replies slow? (NFR5)

Same route (Fontys gateway), same model, same prompt (a real REPLY prompt for Els),
only one difference: thinking on (default) vs thinking turned down.
Calls alternate so both get the same moment. Stored in AiCalls as Source = 'benchmark'.
Costs 2 x ROUNDS requests on the Fontys budget.

Run:  python benchmark_thinking.py
"""
import statistics
import time
from datetime import datetime

from db import get_login, get_patient_context, log_ai_call
from gemini_client import PORTKEY_MODEL, portkey
from prompts import build_summary_prompt

ROUNDS = 5
LOW_EFFORT = "low"   # if the gateway refuses "none", try "low"
PAUSE = 3

els = get_login("els.test@example.com")["PatientID"]
transcript = [
    ("Ana", "Hello Els, how are you doing today?"),
    ("Patient", "I'm good, but my ankles are a bit swollen again."),
]
prompt = build_summary_prompt(get_patient_context(els), transcript)
tokens = len(prompt) // 4
print(f"Prompt: Els's reply prompt, about {tokens} tokens. {ROUNDS} rounds.\n")


def ask(effort):
    extra = {"reasoning_effort": effort} if effort else {}
    r = portkey.chat.completions.create(
        model=PORTKEY_MODEL, messages=[{"role": "user", "content": prompt}], **extra)
    usage = getattr(r, "usage", None)
    out = getattr(usage, "completion_tokens", None)
    details = getattr(usage, "completion_tokens_details", None)
    thinking = getattr(details, "reasoning_tokens", None) if details else None
    return out, thinking


VARIANTS = [("thinking default", None), (f"thinking {LOW_EFFORT}", LOW_EFFORT)]
results = {name: [] for name, _ in VARIANTS}
for i in range(1, ROUNDS + 1):
    order = VARIANTS if i % 2 else VARIANTS[::-1]
    for name, effort in order:
        start = time.time()
        try:
            out, thinking = ask(effort)
            ok, error = True, ""
        except Exception as e:
            out = thinking = None
            ok, error = False, f"{type(e).__name__}: {e}"[:200]
        seconds = round(time.time() - start, 1)
        results[name].append((ok, seconds))
        log_ai_call(datetime.now().replace(microsecond=0), "ok" if ok else "failed", seconds,
                    f"fontys/{name}", error, tokens, source="benchmark", patient_id=els,
                    call_type="benchmark-thinking")
        print(f"round {i}  {name:<18} {'ok    ' if ok else 'FAILED'} {seconds:>5.1f} s  "
              f"output tokens: {out}  thinking tokens: {thinking}  {error[:60]}")
        time.sleep(PAUSE)

print("\nVariant             Success   Median   Within 5 s   Within 10 s")
for name, rows in results.items():
    t = [s for ok, s in rows if ok]
    med = f"{statistics.median(t):.1f} s" if t else "-"
    w5 = f"{100 * sum(s <= 5 for s in t) / len(rows):.0f}%"
    w10 = f"{100 * sum(s <= 10 for s in t) / len(rows):.0f}%"
    print(f"{name:<18} {100 * len(t) / len(rows):>6.0f}%   {med:>7}   {w5:>9}   {w10:>10}")