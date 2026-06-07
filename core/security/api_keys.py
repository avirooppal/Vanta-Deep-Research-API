import secrets
import bcrypt

PREFIX = "drapi_live_"


def generate_api_key(org_prefix: str) -> tuple[str, str]:
    """
    Returns (full_key, key_hash).
    full_key is shown to the user once and never stored.
    key_hash is stored in the database.
    """
    secret = secrets.token_hex(32)
    full_key = f"{PREFIX}{org_prefix[:8]}_{secret}"
    key_hash = bcrypt.hashpw(full_key.encode(), bcrypt.gensalt()).decode()
    return full_key, key_hash


def verify_api_key(full_key: str, key_hash: str) -> bool:
    try:
        return bcrypt.checkpw(full_key.encode(), key_hash.encode())
    except ValueError:
        return False
