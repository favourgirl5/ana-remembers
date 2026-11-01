"""Login for Ana Remembers: password hashing and signed login tokens.

Passwords are only ever stored as bcrypt hashes. A login token is
"<patient_id>.<expiry>.<signature>", signed with AUTH_SECRET from .env, so it
can't be faked and keeps working when the API restarts.
"""
import hashlib
import hmac
import os
import time

import bcrypt
from dotenv import load_dotenv

load_dotenv()
SECRET = os.getenv("AUTH_SECRET", "dev-only-change-me").encode()
TOKEN_HOURS = 24 * 30


def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password, password_hash):
    try:
        return bcrypt.checkpw(password.encode(), (password_hash or "").encode())
    except ValueError:  # e.g. the placeholder 'not-a-real-hash' from the seed data
        return False


def _sign(payload):
    return hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()


def make_token(patient_id):
    expires = int(time.time()) + TOKEN_HOURS * 3600
    payload = f"{patient_id}.{expires}"
    return f"{payload}.{_sign(payload)}"


def read_token(token):
    """Returns the PatientID for a valid, unexpired token, otherwise None."""
    try:
        patient_id, expires, signature = token.split(".")
        payload = f"{patient_id}.{expires}"
        if not hmac.compare_digest(signature, _sign(payload)):
            return None
        if int(expires) < time.time():
            return None
        return int(patient_id)
    except (ValueError, AttributeError):
        return None