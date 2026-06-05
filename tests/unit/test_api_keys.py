from core.security.api_keys import generate_api_key, verify_api_key, PREFIX


def test_key_has_prefix():
    full_key, _ = generate_api_key("orgabc123")
    assert full_key.startswith(PREFIX)


def test_verify_correct_key():
    full_key, key_hash = generate_api_key("orgabc123")
    assert verify_api_key(full_key, key_hash) is True


def test_verify_wrong_key():
    _, key_hash = generate_api_key("orgabc123")
    assert verify_api_key("drapi_live_wrong_key", key_hash) is False


def test_two_keys_are_unique():
    key1, _ = generate_api_key("orgabc123")
    key2, _ = generate_api_key("orgabc123")
    assert key1 != key2
