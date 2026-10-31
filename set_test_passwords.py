"""Give the fake test patients a real (hashed) password so they can log in.

Run once:  python set_test_passwords.py
"""
from auth import hash_password
from db import get_login, set_password_hash

TEST_PASSWORD = "AnaTest123"
TEST_EMAILS = [
    "mario.test@example.com",
    "els.test@example.com",
    "kees.test@example.com",
]

for email in TEST_EMAILS:
    patient = get_login(email)
    if patient is None:
        print(f"Not found (skipped): {email}")
        continue
    set_password_hash(patient["PatientID"], hash_password(TEST_PASSWORD))
    print(f"Password set for {patient['FullName']} ({email})")

print(f"\nTest password for all of them: {TEST_PASSWORD}")