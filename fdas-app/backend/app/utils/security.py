import hashlib
import hmac
import os


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 120000)
    return f"pbkdf2_sha256$120000${salt}${digest.hex()}"


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        scheme, iterations_text, salt, expected_digest = password_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            bytes.fromhex(salt),
            iterations,
        ).hex()
        return hmac.compare_digest(digest, expected_digest)
    except (ValueError, TypeError):
        return False


def hash_demo_password(password: str) -> str:
    return hash_password(password)
