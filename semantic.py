"""Semantic search for Ana Remembers (memory v3).

Matches by meaning instead of spelling: "racing heart" and "palpitations" are close,
"ankle swelling" and "headache" are not. Each text becomes an embedding (a list of numbers
that represents its meaning); two texts are similar when their embeddings point the same way
(cosine similarity, 1.0 = same meaning).

Embeddings are made with the free Gemini embedding model (the Fontys gateway only allows the
chat model). They are stored as JSON in SQL Server; comparing them happens here in Python.
"""
import json
import math

from google.genai import types

from gemini_client import client

EMBED_MODEL = "gemini-embedding-001"
DIMENSIONS = 768          # smaller than the default 3072: enough for short texts, less storage
# Measured with benchmark_semantic.py: no threshold separates "same" from "different" cleanly
# ("ankle swelling" vs "abdominal swelling" = 0.757, "palpitations" vs "racing heart" = 0.709).
# So code only SEARCHES with a low threshold (found 8/8 same pairs) and Gemini JUDGES in context.
CANDIDATE_THRESHOLD = 0.65
MAX_RELATED = 3


def embed(text):
    """Text -> list of numbers. Raises if the embedding model can't be reached."""
    response = client.models.embed_content(
        model=EMBED_MODEL,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=DIMENSIONS),
    )
    return list(response.embeddings[0].values)


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def to_json(vector):
    return json.dumps([round(v, 6) for v in vector])


def from_json(text):
    return json.loads(text) if text else None


def best_match(vector, candidates, threshold=CANDIDATE_THRESHOLD):
    """candidates: list of (label, vector). Returns (label, score) of the closest one
    above the threshold, or None."""
    scored = [(label, cosine(vector, v)) for label, v in candidates if v]
    if not scored:
        return None
    label, score = max(scored, key=lambda x: x[1])
    return (label, score) if score >= threshold else None


def find_related(patient_id, text, ctx):
    """Concerns and older check-ins that mean something similar to what the patient just said,
    and that are NOT already in Ana's prompt. Missing embeddings are made and saved on the way."""
    from db import (get_concerns_for_search, get_older_sessions_for_search,
                    save_concern_embedding, save_session_embedding)

    query = embed(text)
    in_prompt = {c["Concern"] for c in ctx.get("open_concerns", []) + ctx.get("resolved_concerns", [])}

    concerns = []
    for row in get_concerns_for_search(patient_id):
        vector = from_json(row.get("Embedding"))
        if vector is None:
            vector = embed(row["Concern"])
            save_concern_embedding(row["ConcernID"], to_json(vector))
        if row["Concern"] in in_prompt:
            continue
        score = cosine(query, vector)
        if score >= CANDIDATE_THRESHOLD:
            concerns.append({**row, "Score": round(score, 2)})

    sessions = []
    for row in get_older_sessions_for_search(patient_id, skip_recent=len(ctx.get("recent_sessions", []))):
        vector = from_json(row.get("SummaryEmbedding"))
        if vector is None:
            vector = embed(row["ConversationSummary"])
            save_session_embedding(row["SessionID"], to_json(vector))
        score = cosine(query, vector)
        if score >= CANDIDATE_THRESHOLD:
            sessions.append({**row, "Score": round(score, 2)})

    by_score = lambda r: -r["Score"]
    strip = lambda r: {k: v for k, v in r.items() if k not in ("Embedding", "SummaryEmbedding")}
    return {
        "concerns": [strip(r) for r in sorted(concerns, key=by_score)[:MAX_RELATED]],
        "sessions": [strip(r) for r in sorted(sessions, key=by_score)[:MAX_RELATED]],
    }