import hashlib
import secrets


def generate_api_key() -> str:
    return secrets.token_urlsafe(24)


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
