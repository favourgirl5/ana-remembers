import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def get_ai_response(prompt):
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt
    )
    return response.text


if __name__ == "__main__":
    reply = get_ai_response("Say hello as if you're a caring healthcare assistant named Ana.")
    print(reply)