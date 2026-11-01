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


def get_patient_context(patient_id, recent_sessions=5):
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
            "SELECT Concern, Category, Trend, FirstMentioned, LastUpdated, Notes "
            "FROM PatientConcerns WHERE PatientID = ? AND Status = 'open' "
            "ORDER BY LastUpdated DESC",
            patient_id,
        )
        concerns = _rows_to_dicts(cur)

        return {
            "open_concerns": concerns,
            "patient": patient[0],
            "diagnoses": diagnoses,
            "medications": medications,
            "recent_sessions": sessions,
        }
    finally:
        conn.close()


def store_session(patient_id, medication_taken, summary):
    """Insert one check-in. Returns the new SessionID."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO Sessions (PatientID, SessionDate, MedicationTaken, ConversationSummary) "
            "OUTPUT INSERTED.SessionID "
            "VALUES (?, SYSDATETIME(), ?, ?)",
            patient_id, medication_taken, summary,
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
    """Update the patient's ongoing-concerns list after a check-in."""
    if not concerns:
        return
    conn = get_connection()
    try:
        cur = conn.cursor()
        for item in concerns:
            name = str(item.get("concern", "")).strip()[:200]
            if not name:
                continue
            status = "resolved" if item.get("status") == "resolved" else "open"
            trend = (str(item.get("trend") or "").strip()[:20]) or None
            category = (str(item.get("category") or "other").strip()[:30]) or "other"
            note = (str(item.get("note") or "").strip()[:500]) or None
            cur.execute(
                "SELECT ConcernID FROM PatientConcerns WHERE PatientID = ? AND Concern = ?",
                patient_id, name,
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE PatientConcerns SET Status = ?, Trend = COALESCE(?, Trend), "
                    "Notes = COALESCE(?, Notes), LastUpdated = SYSDATETIME() WHERE ConcernID = ?",
                    status, trend, note, row[0],
                )
            else:
                cur.execute(
                    "INSERT INTO PatientConcerns (PatientID, Concern, Category, Status, Trend, "
                    "FirstMentioned, LastUpdated, Notes) "
                    "VALUES (?, ?, ?, ?, ?, SYSDATETIME(), SYSDATETIME(), ?)",
                    patient_id, name, category, status, trend, note,
                )
        conn.commit()
    finally:
        conn.close()