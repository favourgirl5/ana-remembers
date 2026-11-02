"""Reading medical reports for Ana Remembers.

Gemini reads an uploaded PDF or photo and returns what it finds as JSON.
Nothing is saved here: the patient first checks the results in the app, and only
confirmed items are stored (see db.save_extracted_records).
"""
import json

EXTRACT_PROMPT = """You are reading a medical document (for example a hospital discharge letter,
a GP letter or a medication list) for a patient living with heart failure.

Extract ONLY what is clearly written in the document. Never guess, never add anything
that is not in the document, and never "correct" doses or names.

Return ONLY valid JSON, no extra text, in this exact shape:
{"diagnoses": [{"name": "", "date": "YYYY-MM-DD or null", "presenting_symptoms": ""}],
 "medications": [{"name": "", "dosage": "", "frequency": "", "start_date": "YYYY-MM-DD or null"}],
 "allergies": [""],
 "care_contacts": [{"role": "GP | Hospital | Heart failure nurse | Other", "name": "", "phone": ""}],
 "unclear": ["anything that was hard to read or that you were unsure about"]}

Use [] for anything the document does not contain. Use null for unknown dates."""

EMPTY_RESULT = {"diagnoses": [], "medications": [], "allergies": [], "care_contacts": [], "unclear": []}


def _items(value, fields, limit=30):
    out = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        clean = {}
        for f in fields:
            v = item.get(f)
            clean[f] = str(v).strip() if v not in (None, "", "null") else None
        if clean.get(fields[0]):  # needs at least a name
            out.append(clean)
    return out[:limit]


def _strings(value, limit=20):
    return [str(v).strip() for v in (value if isinstance(value, list) else [])
            if v is not None and str(v).strip().lower() not in ("", "null", "none", "none known")][:limit]


def parse_extraction(text):
    """Turn Gemini's JSON into clean lists. Falls back safely if the JSON is broken."""
    cleaned = (text or "").strip()
    try:
        data = json.loads(cleaned[cleaned.find("{"): cleaned.rfind("}") + 1])
    except (ValueError, AttributeError):
        result = dict(EMPTY_RESULT)
        result["unclear"] = ["Ana could not read this document. Please try a clearer photo or a PDF."]
        return result
    return {
        "diagnoses": _items(data.get("diagnoses"), ["name", "date", "presenting_symptoms"]),
        "medications": _items(data.get("medications"), ["name", "dosage", "frequency", "start_date"]),
        "allergies": _strings(data.get("allergies")),
        "care_contacts": _items(data.get("care_contacts"), ["name", "role", "phone"]),
        "unclear": _strings(data.get("unclear")),
    }