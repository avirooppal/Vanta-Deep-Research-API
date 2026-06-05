import base64
import hashlib
from cryptography.fernet import Fernet
from core.config import settings


def _get_fernet() -> Fernet:
    # Derive a 32-byte key from SECRET_KEY
    key_bytes = hashlib.sha256(settings.secret_key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def encrypt(plaintext: str) -> bytes:
    return _get_fernet().encrypt(plaintext.encode())


def decrypt(ciphertext: bytes) -> str:
    return _get_fernet().decrypt(ciphertext).decode()
