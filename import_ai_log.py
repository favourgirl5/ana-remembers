"""One-off: copy the existing gemini_log.csv into the AiCalls table, so no data is lost.
Run once:  python import_ai_log.py"""
import csv
from datetime import datetime

from db import get_connection, log_ai_call

conn = get_connection()
already = conn.cursor().execute("SELECT COUNT(*) FROM AiCalls WHERE Source = 'csv-import'").fetchone()[0]
conn.close()
if already:
    raise SystemExit(f"Already imported ({already} rows). Nothing done.")

count = 0
with open("gemini_log.csv", newline="") as f:
    for r in csv.reader(f):
        if len(r) < 4:
            continue
        try:
            t = datetime.fromisoformat(r[0]); seconds = float(r[2])
        except ValueError:
            continue
        tokens = int(r[5]) if len(r) > 5 and r[5].isdigit() else None
        log_ai_call(t, r[1], seconds, r[3], r[4] if len(r) > 4 else "", tokens, source="csv-import")
        count += 1
print(f"Imported {count} calls from gemini_log.csv into AiCalls.")