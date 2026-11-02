"""Benchmark: memory options for Ana (no Gemini calls, costs no quota).
Compares 'last N sessions only' with 'concerns list + last 5 sessions'."""
from db import get_patient_context
from prompts import build_checkin_prompt

PATIENTS = {1: "Mario", 2: "Els", 4: "Kees"}
OPTIONS = [("Last 3 sessions", 3, False), ("Last 5 sessions", 5, False),
           ("Last 10 sessions", 10, False), ("All sessions", 1000, False),
           ("Concerns list + last 5 (current)", 5, True)]


def keywords(concern):
    words = [w for w in concern.lower().replace("-", " ").split() if len(w) > 3]
    return [w[:5] for w in words if w not in ("about", "with", "night", "taking")]


def covered(concern, ctx, use_list):
    if use_list:
        return True  # listed in ONGOING CONCERNS, so Ana always sees it
    text = " ".join(str(s.get("ConversationSummary") or "") for s in ctx["recent_sessions"]).lower()
    return any(k in text for k in keywords(concern))


print(f"{'Patient':<8}{'Option':<36}{'Sessions':>9}{'Tokens':>9}{'Concerns seen':>15}")
for pid, name in PATIENTS.items():
    open_concerns = get_patient_context(pid)["open_concerns"]
    for label, n, use_list in OPTIONS:
        ctx = get_patient_context(pid, recent_sessions=n)
        if not use_list:
            ctx["open_concerns"] = []
        tokens = len(build_checkin_prompt(ctx)) // 4  # rough estimate: 1 token ~ 4 characters
        seen = sum(covered(c["Concern"], ctx, use_list) for c in open_concerns)
        print(f"{name:<8}{label:<36}{len(ctx['recent_sessions']):>9}{tokens:>9}"
              f"{f'{seen}/{len(open_concerns)}':>15}")
    print()