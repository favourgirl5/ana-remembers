"""Escalation rules for Ana Remembers.

"Model judges, code acts":
- Gradual decline is decided here, by a fixed Python rule on the concerns list.
- Acute red flags are reported by Gemini in the summary JSON ("escalation").
Python combines both and saves the result with the session, where the care team
can see it.
"""
from datetime import datetime

TREND_MIN_COUNT = 3   # worse at least this many times...
TREND_MIN_DAYS = 21   # ...within this many days, even with better days in between

LEVELS = {None: 0, "none": 0, "urgent": 1, "emergency": 2}


def worsening_trends(open_concerns):
    """Symptoms that have been getting worse for weeks (no improvement in between)."""
    now = datetime.now()
    hits = []
    for c in open_concerns or []:
        if c.get("Category") != "symptom":
            continue
        since = c.get("WorseSince")
        if not since or (c.get("WorseCount") or 0) < TREND_MIN_COUNT:
            continue
        if (now - datetime.fromisoformat(str(since))).days <= TREND_MIN_DAYS:
            hits.append(c["Concern"])
    return hits


def trend_escalation(open_concerns):
    """Returns (level, reason) for gradual decline, or (None, None)."""
    hits = worsening_trends(open_concerns)
    if not hits:
        return None, None
    return "urgent", f"Worse {TREND_MIN_COUNT} times within {TREND_MIN_DAYS} days: {', '.join(hits)}"


def higher(current, new):
    """Keep the more serious of two (level, reason) pairs."""
    if LEVELS.get(new[0], 0) > LEVELS.get(current[0], 0):
        return new
    return current


def primary_contact(contacts):
    """The first person to contact for an urgent escalation."""
    for c in contacts or []:
        if c.get("IsPrimary"):
            return c
    return (contacts or [None])[0]