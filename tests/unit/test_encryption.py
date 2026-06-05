from core.security.encryption import encrypt, decrypt


def test_roundtrip():
    plaintext = "sk-my-secret-api-key-12345"
    ciphertext = encrypt(plaintext)
    assert isinstance(ciphertext, bytes)
    assert decrypt(ciphertext) == plaintext


def test_ciphertext_differs_from_plaintext():
    result = encrypt("hello")
    assert result != b"hello"
