import hmac
import hashlib


def hmac_sign(payload: str, timestamp: str, secret: str) -> str:
    key = secret.encode("utf-8")
    msg = f"{timestamp}.{payload}".encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()
