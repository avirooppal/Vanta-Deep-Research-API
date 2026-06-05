from core.security.api_keys import generate_api_key, verify_api_key


def test_verify_logic_used_in_middleware():
    full_key, key_hash = generate_api_key("testorg1")
    assert verify_api_key(full_key, key_hash)
    assert not verify_api_key("drapi_live_bad_key_000", key_hash)
