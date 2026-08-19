import hashlib
import secrets
#secrets- cryptographically secure random number generator

def generate_api_key() -> tuple[str, str, str]:
    full_key = f"lgw_{secrets.token_urlsafe(32)}"
    key_prefix = full_key[:12]
    key_hash = hash_api_key(full_key)
    return full_key, key_prefix, key_hash

def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()
