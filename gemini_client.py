import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Tried in order. If one is busy or out of quota, the next one answers.
# Each model has its own free daily quota.
MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-flash-latest",
]

last_model_used = None  # which model answered last (handy for the test sheet)


def get_ai_response(prompt):
    global last_model_used
    last_error = None
    for model in MODELS:
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            last_model_used = model
            if model != MODELS[0]:
                print(f"[Backup model used: {model}]")
            return response.text
        except Exception as e:
            last_error = e
            print(f"[{model} unavailable: {str(e)[:60]}... trying next model]")
    raise last_error


if __name__ == "__main__":
    reply = get_ai_response("Say hello as if you're a caring healthcare assistant named Ana.")
    print(reply)

    from google.genai import types

def get_ai_response_with_file(prompt, data, mime_type):
    """Same as get_ai_response, but also sends a PDF or photo for Gemini to read."""
    global last_model_used
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