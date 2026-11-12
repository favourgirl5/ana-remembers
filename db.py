"""Database access for Ana Remembers (SQL Server Express, Windows auth)."""
import pyodbc

CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost\\SQLEXPRESS02;"
    "DATABASE=AnaRemembers;"
    "Trusted_Connection=yes;"
)


def get_connection():
    return pyodbc.connect(CONN_STR, timeout=30)


def _rows_to_dicts(cursor):
    """Turn pyodbc rows into plain dicts, with dates/decimals made prompt-safe."""
    cols = [c[0] for c in cursor.description]
    out = []
    for row in cursor.fetchall():
        item = {}
        for col, val in zip(cols, row):
            if hasattr(val, "isoformat"):          # date / datetime
                val = val.isoformat()
            elif type(val).__name__ == "Decimal":
                val = float(val)
            item[col] = val
        out.append(item)
    return out


def show_schema():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE "
            "FROM INFORMATION_SCHEMA.COLUMNS ORDER BY TABLE_NAME, ORDINAL_POSITION"
        )
        current = None
        for table, col, dtype in cur.fetchall():
            if table != current:
                print(f"\n{table}")
                current = table
            print(f"  {col} ({dtype})")
    finally:
        conn.close()


def get_patient_context(patient_id, recent_sessions=3):
    """Everything Ana needs for a check-in. Email and PasswordHash are never selected."""
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            "SELECT PatientID, FullName, DateOfBirth, BaselineWeightKg, Allergies "
            "FROM Patients WHERE PatientID = ?",
            patient_id,
        )
        patient = _rows_to_dicts(cur)
        if not patient:
            return None

        cur.execute(
            "SELECT DiagnosisName, DiagnosisDate, PresentingSymptoms "
            "FROM Diagnoses WHERE PatientID = ? ORDER BY DiagnosisDate DESC",
            patient_id,
        )
        diagnoses = _rows_to_dicts(cur)

        cur.execute(
            "SELECT MedicationName, Dosage, Frequency, StartDate "
            "FROM Medications WHERE PatientID = ? ORDER BY StartDate DESC",
            patient_id,
        )
        medications = _rows_to_dicts(cur)

        cur.execute(
            "SELECT TOP (?) SessionDate, MedicationTaken, ConversationSummary "
            "FROM Sessions WHERE PatientID = ? ORDER BY SessionDate DESC",
            recent_sessions, patient_id,
        )
        sessions = _rows_to_dicts(cur)

        cur.execute(
            "SELECT Concern, Category, Status, Trend, FirstMentioned, LastUpdated, Notes, "
            "WorseCount, WorseSince "
            "FROM PatientConcerns WHERE PatientID = ? AND Status IN ('open', 'improving') "
            "ORDER BY LastUpdated DESC",
            patient_id,
        )
        concerns = _rows_to_dicts(cur)

        # v3: concerns closed in the last 90 days, so Ana notices when one comes back
        cur.execute(
            "SELECT Concern, Category, FirstMentioned, LastUpdated, Notes, ResolvedBy "
            "FROM PatientConcerns WHERE PatientID = ? AND Status = 'resolved' "
            "AND LastUpdated >= DATEADD(DAY, -90, GETDATE()) ORDER BY LastUpdated DESC",
            patient_id,
        )
        resolved = _rows_to_dicts(cur)

        cur.execute(
            "SELECT Role, Name, Phone, IsPrimary "
            "FROM CareContacts WHERE PatientID = ? ORDER BY IsPrimary DESC, Role",
            patient_id,
        )
        contacts = _rows_to_dicts(cur)

        return {
            "open_concerns": concerns,
            "resolved_concerns": resolved,
            "care_contacts": contacts,
            "patient": patient[0],
            "diagnoses": diagnoses,
            "medications": medications,
            "recent_sessions": sessions,
        }
    finally:
        conn.close()


def store_session(patient_id, medication_taken, summary,
                  escalation_level=None, escalation_reason=None):
    """Insert one check-in (with any escalation). Returns the new SessionID."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO Sessions (PatientID, SessionDate, MedicationTaken, ConversationSummary, "
            "EscalationLevel, EscalationReason) "
            "OUTPUT INSERTED.SessionID "
            "VALUES (?, SYSDATETIME(), ?, ?, ?, ?)",
            patient_id, medication_taken, summary, escalation_level,
            (escalation_reason or "")[:500] or None,
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        return new_id
    finally:
        conn.close()


def get_session_dates(patient_id, days=60):
    """Dates (YYYY-MM-DD) on which the patient had a check-in, newest first."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT CAST(SessionDate AS DATE) AS Day FROM Sessions "
            "WHERE PatientID = ? AND SessionDate >= DATEADD(DAY, ?, CAST(GETDATE() AS DATE)) "
            "ORDER BY Day DESC",
            patient_id, -days,
        )
        return [row[0].isoformat() for row in cur.fetchall()]
    finally:
        conn.close()


def get_login(email):
    """Login details for one patient. Only used to check passwords; never sent to Gemini."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT PatientID, FullName, Email, PasswordHash FROM Patients WHERE Email = ?",
            email,
        )
        rows = _rows_to_dicts(cur)
        return rows[0] if rows else None
    finally:
        conn.close()


def set_password_hash(patient_id, password_hash):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE Patients SET PasswordHash = ? WHERE PatientID = ?",
            password_hash, patient_id,
        )
        conn.commit()
    finally:
        conn.close()


def upsert_concerns(patient_id, concerns):
    """Update the patient's ongoing-concerns list after a check-in.

    "Model judges, code acts":
    - Getting worse: 'worse' adds 1 to WorseCount (the trend rule escalates at 3 over 21 days).
    - Getting better: Gemini can't close a concern on the patient's word alone. 'better' or
      'resolved' only marks it 'improving' and adds 1 to BetterCount. Python closes it after
      3 check-ins in a row over 14+ days (ResolvedBy = 'auto'), or a clinician closes it
      (ResolvedBy = 'clinician', see close_concern_by_clinician).
    - If it is 'same' or 'worse' again, it goes back to 'open' and BetterCount resets.
    - A resolved concern that comes back is reopened (same name), so its history stays.
    """
    if not concerns:
        return
    conn = get_connection()
    try:
        cur = conn.cursor()
        for item in concerns:
            name = str(item.get("concern", "")).strip()[:200]
            if not name:
                continue
            said_gone = item.get("status") == "resolved"
            trend = (str(item.get("trend") or "").strip()[:20]) or None
            category = (str(item.get("category") or "other").strip()[:30]) or "other"
            note = (str(item.get("note") or "").strip()[:500]) or None
            getting_better = said_gone or trend == "better"
            getting_worse = trend in ("worse", "returned", "new")

            cur.execute(
                "SELECT ConcernID, Status FROM PatientConcerns WHERE PatientID = ? AND Concern = ?",
                patient_id, name,
            )
            row = cur.fetchone()
            if not row:
                cur.execute(
                    "INSERT INTO PatientConcerns (PatientID, Concern, Category, Status, Trend, "
                    "FirstMentioned, LastUpdated, Notes, WorseCount, WorseSince, BetterCount) "
                    "VALUES (?, ?, ?, 'open', ?, SYSDATETIME(), SYSDATETIME(), ?, ?, "
                    "CASE WHEN ? = 1 THEN SYSDATETIME() END, 0)",
                    patient_id, name, category, trend, note,
                    1 if trend == "worse" else 0, 1 if trend == "worse" else 0,
                )
                continue

            concern_id, status = row
            cur.execute(
                "UPDATE PatientConcerns SET Trend = COALESCE(?, Trend), Notes = COALESCE(?, Notes), "
                "LastUpdated = SYSDATETIME() WHERE ConcernID = ?",
                trend, note, concern_id,
            )

            if getting_better:
                # Patient says better/gone: 'improving', never closed on their word alone
                cur.execute(
                    "UPDATE PatientConcerns SET Status = 'improving', BetterCount = BetterCount + 1, "
                    "BetterSince = COALESCE(BetterSince, SYSDATETIME()) "
                    "WHERE ConcernID = ? AND Status <> 'resolved'",
                    concern_id,
                )
                # Python closes it: better in 3 check-ins in a row, over at least 14 days
                cur.execute(
                    "UPDATE PatientConcerns SET Status = 'resolved', ResolvedBy = 'auto' "
                    "WHERE ConcernID = ? AND Status = 'improving' AND BetterCount >= ? "
                    "AND DATEDIFF(DAY, BetterSince, SYSDATETIME()) >= ?",
                    concern_id, CLOSE_MIN_COUNT, CLOSE_MIN_DAYS,
                )
            else:
                # Mentioned and not better: (re)open it; a resolved concern that returns is reopened
                cur.execute(
                    "UPDATE PatientConcerns SET Status = 'open', BetterCount = 0, BetterSince = NULL, "
                    "ResolvedBy = NULL WHERE ConcernID = ?",
                    concern_id,
                )
                if trend == "worse":
                    # Count 'worse' reports in a 21-day window; good days in between don't reset it.
                    # An older window has expired, so the count starts again.
                    cur.execute(
                        "UPDATE PatientConcerns SET "
                        "WorseCount = CASE WHEN WorseSince IS NULL OR DATEDIFF(DAY, WorseSince, SYSDATETIME()) > 21 "
                        "THEN 1 ELSE WorseCount + 1 END, "
                        "WorseSince = CASE WHEN WorseSince IS NULL OR DATEDIFF(DAY, WorseSince, SYSDATETIME()) > 21 "
                        "THEN SYSDATETIME() ELSE WorseSince END "
                        "WHERE ConcernID = ?",
                        concern_id,
                    )
                # 'unknown' / 'returned' / no trend: leave the worse counter as it is
        conn.commit()
    finally:
        conn.close()


CLOSE_MIN_COUNT = 3   # better/gone in at least this many check-ins in a row...
CLOSE_MIN_DAYS = 14   # ...over at least this many days


def close_concern_by_clinician(patient_id, concern):
    """A GP or nurse confirms a concern is resolved (e.g. after a visit or a report)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE PatientConcerns SET Status = 'resolved', ResolvedBy = 'clinician', "
            "LastUpdated = SYSDATETIME() WHERE PatientID = ? AND Concern = ?",
            patient_id, concern,
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()

# ---------- Monitoring ----------

def log_ai_call(call_time, result, seconds, model, error, prompt_tokens, source="live",
                patient_id=None, call_type=None):
    """One row per AI call, for the monitoring report (Power BI)."""
    conn = get_connection()
    try:
        conn.cursor().execute(
            "INSERT INTO AiCalls (CallTime, Result, Seconds, Model, Error, PromptTokens, Source, "
            "PatientID, CallType) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            call_time, result, seconds, model or None, (error or None) and error[:200], prompt_tokens, source,
            patient_id, call_type,
        )
        conn.commit()
    finally:
        conn.close()
        
# ---------- Semantic search (memory v3) ----------

def get_concerns_for_search(patient_id):
    """All of a patient's concerns, any status, with their stored embedding (may be NULL)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT ConcernID, Concern, Category, Status, Trend, FirstMentioned, LastUpdated, Notes, "
            "Embedding FROM PatientConcerns WHERE PatientID = ?",
            patient_id,
        )
        return _rows_to_dicts(cur)
    finally:
        conn.close()


def get_older_sessions_for_search(patient_id, skip_recent=5):
    """Check-ins older than the ones already in the prompt, with their embedding (may be NULL)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT SessionID, SessionDate, ConversationSummary, SummaryEmbedding FROM Sessions "
            "WHERE PatientID = ? AND ConversationSummary IS NOT NULL "
            "ORDER BY SessionDate DESC OFFSET ? ROWS",
            patient_id, skip_recent,
        )
        return _rows_to_dicts(cur)
    finally:
        conn.close()


def save_concern_embedding(concern_id, embedding_json):
    conn = get_connection()
    try:
        conn.cursor().execute("UPDATE PatientConcerns SET Embedding = ? WHERE ConcernID = ?",
                              embedding_json, concern_id)
        conn.commit()
    finally:
        conn.close()


def save_session_embedding(session_id, embedding_json):
    conn = get_connection()
    try:
        conn.cursor().execute("UPDATE Sessions SET SummaryEmbedding = ? WHERE SessionID = ?",
                              embedding_json, session_id)
        conn.commit()
    finally:
        conn.close()

# ---------- Registration and medical reports ----------

def create_patient(full_name, email, password_hash, date_of_birth, baseline_weight_kg=None):
    """New patient account. Returns the new PatientID."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO Patients (FullName, DateOfBirth, CreatedAt, Email, PasswordHash, "
            "BaselineWeightKg, Allergies) OUTPUT INSERTED.PatientID "
            "VALUES (?, ?, SYSDATETIME(), ?, ?, ?, NULL)",
            full_name, date_of_birth, email, password_hash, baseline_weight_kg,
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        return new_id
    finally:
        conn.close()


def _clean(value, limit):
    text = str(value or "").strip()
    return text[:limit] or None


def _date_or_none(value):
    text = str(value or "").strip()
    if len(text) == 10 and text[4] == "-" and text[7] == "-" and text.replace("-", "").isdigit():
        return text
    return None

def _name_key(text):
    """'Dr. P. Hendriks, Huisartsenpraktijk De Berk (fictional)' -> 'dr. p. hendriks'.
    Gemini doesn't write names identically every time, so compare only the core name."""
    core = str(text or "").split(",")[0].split("(")[0]
    return " ".join(core.lower().split())

def save_extracted_records(patient_id, records):
    """Save the report items the patient confirmed. Skips items already in the record.
    Returns how many of each were added."""
    saved = {"diagnoses": 0, "medications": 0, "allergies": 0, "care_contacts": 0}
    conn = get_connection()
    try:
        cur = conn.cursor()

        for d in records.get("diagnoses") or []:
            name = _clean(d.get("name"), 100)
            if not name:
                continue
            cur.execute("SELECT DiagnosisName FROM Diagnoses WHERE PatientID = ?", patient_id)
            if any(_name_key(n) == _name_key(name) for (n,) in cur.fetchall()):
                continue
            cur.execute(
                "INSERT INTO Diagnoses (PatientID, DiagnosisName, DiagnosisDate, PresentingSymptoms) "
                "VALUES (?, ?, COALESCE(?, CAST(GETDATE() AS DATE)), ?)",
                patient_id, name, _date_or_none(d.get("date")), _clean(d.get("presenting_symptoms"), 255),
            )
            saved["diagnoses"] += 1

        for m in records.get("medications") or []:
            name = _clean(m.get("name"), 100)
            if not name:
                continue
            cur.execute("SELECT MedicationName FROM Medications WHERE PatientID = ?", patient_id)
            if any(_name_key(n) == _name_key(name) for (n,) in cur.fetchall()):
                continue
            cur.execute(
                "INSERT INTO Medications (PatientID, MedicationName, Dosage, Frequency, StartDate) "
                "VALUES (?, ?, ?, ?, COALESCE(?, CAST(GETDATE() AS DATE)))",
                patient_id, name, _clean(m.get("dosage"), 50), _clean(m.get("frequency"), 100),
                _date_or_none(m.get("start_date")),
            )
            saved["medications"] += 1

        new_allergies = [a for a in (records.get("allergies") or []) if str(a).strip()]
        if new_allergies:
            cur.execute("SELECT Allergies FROM Patients WHERE PatientID = ?", patient_id)
            row = cur.fetchone()
            current = [a.strip() for a in str((row[0] if row else "") or "").split(",") if a.strip()]
            current = [a for a in current if a.lower() not in ("none", "none known", "none recorded")]
            for a in new_allergies:
                if a.strip().lower() not in [c.lower() for c in current]:
                    current.append(a.strip())
                    saved["allergies"] += 1
            cur.execute("UPDATE Patients SET Allergies = ? WHERE PatientID = ?",
                        ", ".join(current)[:255], patient_id)

        for c in records.get("care_contacts") or []:
            name = _clean(c.get("name"), 150)
            if not name:
                continue
            phone = _clean(c.get("phone"), 30)
            cur.execute("SELECT Name, Phone FROM CareContacts WHERE PatientID = ?", patient_id)
            if any(_name_key(n) == _name_key(name) or (phone and p == phone)
                   for n, p in cur.fetchall()):
                continue  # same person, even if Gemini wrote the name differently
            role = _clean(c.get("role"), 50) or "Other"
            cur.execute("SELECT 1 FROM CareContacts WHERE PatientID = ? AND IsPrimary = 1", patient_id)
            make_primary = 1 if (role == "GP" and not cur.fetchone()) else 0
            cur.execute(
                "INSERT INTO CareContacts (PatientID, Role, Name, Phone, IsPrimary) VALUES (?, ?, ?, ?, ?)",
                patient_id, role, name, _clean(c.get("phone"), 30), make_primary,
            )
            saved["care_contacts"] += 1

        conn.commit()
        return saved
    finally:
        conn.close()