import hashlib
import os


def hash_demo_password(password: str) -> str:
    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 120000)
    return f"pbkdf2_sha256$120000${salt}${digest.hex()}"
