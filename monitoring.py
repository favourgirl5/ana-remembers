"""Monitoring for Ana Remembers (Managing & Controlling).

Calculates Ana's quality indicators from live data and compares them with their targets:
- AiCalls table   (every Gemini chat call: time, ok/failed, seconds, model, error, prompt tokens)
- SQL Server      (check-ins, escalations, medication, concerns)
Shown on the /monitoring page of the backend.
"""
import os
import statistics
from collections import defaultdict
from datetime import datetime, timedelta

from db import get_connection

PRIMARY_MODEL = os.getenv("PORTKEY_MODEL", "fontys-google/gemini-3.7-flash")

# Targets (see the NFR targets table). "higher" = the value must be at least the target.
TARGETS = {
    "availability_pct": (99.0, "higher", "NFR1 Availability"),
    "median_seconds": (5.0, "lower", "NFR5 Performance (typical reply)"),
    "avg_prompt_tokens": (4000, "lower", "NFR3 Prompt size (tokens)"),
    "p95_seconds": (10.0, "lower", "NFR5 Performance (slowest 5%)"),
    "backup_pct": (5.0, "lower", "NFR1 Backup model needed"),
    "medication_unknown_pct": (10.0, "lower", "Medication intake unknown"),
}


def _read_log(days):
    """AI calls from the AiCalls table (live calls only, not benchmark runs)."""
    since = datetime.now() - timedelta(days=days)
    rows = _sql("SELECT CallTime, Result, CAST(Seconds AS FLOAT), Model, Error, PromptTokens FROM AiCalls "
                "WHERE CallTime >= ? AND Source <> 'benchmark' ORDER BY CallTime", since)
    return [{"time": t, "ok": r == "ok", "seconds": float(s), "model": mdl or "", "error": err or "",
             "tokens": tok} for t, r, s, mdl, err, tok in rows]


def _p95(values):
    if not values:
        return None
    values = sorted(values)
    return values[min(len(values) - 1, int(round(0.95 * (len(values) - 1))))]


def _status(key, value):
    if value is None:
        return "no data"
    target, direction, _ = TARGETS[key]
    ok = value >= target if direction == "higher" else value <= target
    return "met" if ok else "not met"


def _sql(query, *params):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(query, *params)
        return cur.fetchall()
    finally:
        conn.close()


def get_metrics(days=30):
    log = _read_log(days)
    ok_calls = [r for r in log if r["ok"]]
    seconds = [r["seconds"] for r in ok_calls]

    with_tokens = [r for r in ok_calls if r["tokens"]]
    kpis = {
        "availability_pct": round(100 * len(ok_calls) / len(log), 1) if log else None,
        "median_seconds": round(statistics.median(seconds), 1) if seconds else None,
        "avg_prompt_tokens": round(statistics.mean(r["tokens"] for r in with_tokens)) if with_tokens else None,
        "p95_seconds": round(_p95(seconds), 1) if seconds else None,
        "backup_pct": (round(100 * sum(1 for r in ok_calls if r["model"] != PRIMARY_MODEL) / len(ok_calls), 1)
                       if ok_calls else None),
    }

    # Per day: calls, availability, median response time
    by_day = defaultdict(list)
    for r in log:
        by_day[r["time"].date().isoformat()].append(r)
    daily = []
    for day in sorted(by_day):
        rows = by_day[day]
        good = [r["seconds"] for r in rows if r["ok"]]
        daily.append({"day": day, "calls": len(rows),
                      "availability_pct": round(100 * len(good) / len(rows), 1),
                      "median_seconds": round(statistics.median(good), 1) if good else None})

    # NFR3 vs NFR5: does a bigger prompt make Ana slower? (only calls on the main model, so
    # backup-model delays don't distort it)
    main_calls = [r for r in with_tokens if r["model"] == PRIMARY_MODEL]
    token_points = [{"tokens": r["tokens"], "seconds": r["seconds"]} for r in main_calls]
    bands = [("< 2,500", 0, 2500), ("2,500 - 3,500", 2500, 3500), ("3,500 - 4,000", 3500, 4000), ("> 4,000", 4000, 10**9)]
    token_bands = []
    for label, low, high in bands:
        s = [r["seconds"] for r in main_calls if low <= r["tokens"] < high]
        token_bands.append({"band": label, "calls": len(s),
                            "median_seconds": round(statistics.median(s), 1) if s else None})
    correlation = None
    if len(main_calls) >= 5:
        try:
            correlation = round(statistics.correlation([r["tokens"] for r in main_calls],
                                                       [r["seconds"] for r in main_calls]), 2)
        except statistics.StatisticsError:
            correlation = None

    by_model = defaultdict(lambda: {"calls": 0, "failed": 0})
    for r in log:
        by_model[r["model"] or "(none: failed)"]["calls"] += 1
        by_model[r["model"] or "(none: failed)"]["failed"] += 0 if r["ok"] else 1

    # SQL Server: check-ins, escalations, medication, concerns
    since = datetime.now() - timedelta(days=days)
    total, unknown = _sql(
        "SELECT COUNT(*), SUM(CASE WHEN MedicationTaken IS NULL THEN 1 ELSE 0 END) "
        "FROM Sessions WHERE SessionDate >= ?", since)[0]
    kpis["medication_unknown_pct"] = round(100 * (unknown or 0) / total, 1) if total else None

    escalations = {lvl: n for lvl, n in _sql(
        "SELECT EscalationLevel, COUNT(*) FROM Sessions WHERE SessionDate >= ? "
        "AND EscalationLevel IS NOT NULL GROUP BY EscalationLevel", since)}
    checkins_per_day = [{"day": str(d)[:10], "checkins": n} for d, n in _sql(
        "SELECT CAST(SessionDate AS DATE), COUNT(*) FROM Sessions WHERE SessionDate >= ? "
        "GROUP BY CAST(SessionDate AS DATE) ORDER BY 1", since)]
    concerns = {f"{s}": n for s, n in _sql(
        "SELECT Status, COUNT(*) FROM PatientConcerns GROUP BY Status")}
    concerns["returned"] = _sql("SELECT COUNT(*) FROM PatientConcerns WHERE Trend = 'returned'")[0][0]

    return {
        "period_days": days,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "gemini_calls": len(log),
        "failed_calls": len(log) - len(ok_calls),
        "kpis": [{"key": k, "label": TARGETS[k][2], "value": v, "target": TARGETS[k][0],
                  "direction": TARGETS[k][1], "status": _status(k, v)} for k, v in kpis.items()],
        "daily": daily,
        "token_points": token_points,
        "token_bands": token_bands,
        "token_time_correlation": correlation,
        "by_model": dict(by_model),
        "checkins_total": total,
        "checkins_per_day": checkins_per_day,
        "escalations": escalations,
        "concerns": concerns,
        "not_live": [
            "Escalation recall (NFR2): measured in the test sheet (red-flag tests)",
            "Usability score SUS (NFR4): measured with testers",
            "Cross-patient leaks (NFR6): measured in the test sheet (3.2)",
        ],
    }