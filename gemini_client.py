
import base64
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types
from portkey_ai import Portkey

load_dotenv()

# ---------- 1. Fontys gateway (Portkey) ----------
PORTKEY_MODEL = os.getenv("PORTKEY_MODEL", "fontys-google/gemini-3.7-flash")
# debug=False: Portkey doesn't store the conversation content (patient data, NFR6)
portkey = Portkey(api_key=os.getenv("PORTKEY_API_KEY"), debug=False) if os.getenv("PORTKEY_API_KEY") else None

# ---------- 2. Free Gemini API (backup) ----------
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-flash-latest",
]

last_model_used = None  # shown in logs (gemini_log.csv)


def _ask_portkey(content):
    response = portkey.chat.completions.create(
        model=PORTKEY_MODEL, messages=[{"role": "user", "content": content}],
        reasoning_effort=os.getenv("REASONING_EFFORT", "low"))
    return response.choices[0].message.content


def get_ai_response(prompt):
    """Send a text prompt and return the model's reply."""
    global last_model_used
    if portkey:
        try:
            text = _ask_portkey(prompt)
            last_model_used = PORTKEY_MODEL
            return text
        except Exception as e:
            print(f"[Fontys gateway failed, using free Gemini: {e}]")

    last_error = None
    for model in MODELS:
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            last_model_used = model
            return response.text
        except Exception as e:
            last_error = e
            print(f"[{model} failed: {e}]")
    raise last_error

def get_ai_response_with_file(prompt, data, mime_type):
    """Same as get_ai_response, but also sends a PDF or photo for the model to read."""
    global last_model_used
    if portkey:
        try:
            file_uri = f"data:{mime_type};base64,{base64.b64encode(data).decode()}"
            text = _ask_portkey([{"type": "text", "text": prompt},
                                 {"type": "image_url", "image_url": {"url": file_uri}}])
            last_model_used = PORTKEY_MODEL
            return text
        except Exception as e:
            print(f"[Fontys gateway failed for file, using free Gemini: {e}]")

    part = types.Part.from_bytes(data=data, mime_type=mime_type)
    last_error = None
    for model in MODELS:
        try:
            response = client.models.generate_content(model=model, contents=[part, prompt])
            last_model_used = model
            return response.text
        except Exception as e:
            last_error = e
            print(f"[{model} failed: {e}]")
    raise last_error