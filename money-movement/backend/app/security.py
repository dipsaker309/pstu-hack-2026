# pyright: reportMissingImports=false, reportMissingModuleSource=false
import base64
import hashlib
import hmac
import json
import os
import secrets
import time


SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-before-production")
TOKEN_EXPIRE_SECONDS = 60 * 60 * 12


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()
    return f"{salt}${password_hash}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, password_hash = stored_hash.split("$", 1)
    except ValueError:
        return False

    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()
    return hmac.compare_digest(candidate, password_hash)


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": user_id,
        "exp": int(time.time()) + TOKEN_EXPIRE_SECONDS,
    }
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _sign(body)
    return f"{body}.{signature}"


def decode_access_token(token: str) -> int | None:
    try:
        body, signature = token.split(".", 1)
    except ValueError:
        return None

    if not hmac.compare_digest(_sign(body), signature):
        return None

    try:
        payload = json.loads(_b64decode(body).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None

    if int(payload.get("exp", 0)) < int(time.time()):
        return None

    user_id = payload.get("sub")
    return int(user_id) if user_id is not None else None


def _sign(body: str) -> str:
    digest = hmac.new(
        SECRET_KEY.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _b64encode(digest)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
