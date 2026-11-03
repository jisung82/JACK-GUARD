import base64
import hashlib
import hmac
import secrets

ITERATIONS = 600_000


def hash_password(password: str) -> dict:
    if not 8 <= len(password) <= 256:
        raise ValueError("비밀번호는 8~256자여야 합니다.")
    salt = secrets.token_bytes(32)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return {
        "salt": base64.b64encode(salt).decode(),
        "digest": base64.b64encode(digest).decode(),
        "iterations": ITERATIONS,
    }


def valid_record(record: dict) -> bool:
    try:
        return (
            type(record["iterations"]) is int
            and record["iterations"] == ITERATIONS
            and len(base64.b64decode(record["salt"], validate=True)) == 32
            and len(base64.b64decode(record["digest"], validate=True)) == 32
        )
    except (ValueError, KeyError, TypeError):
        return False


def verify_password(password: str, record: dict) -> bool:
    if not valid_record(record) or len(password) > 256:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), base64.b64decode(record["salt"]), record["iterations"]
    )
    return hmac.compare_digest(digest, base64.b64decode(record["digest"]))
