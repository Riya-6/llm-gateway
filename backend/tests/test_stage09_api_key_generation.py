from app.domains.api_keys.security import generate_api_key, hash_api_key


def test_generated_keys_are_unique() -> None:
    first, _, _ = generate_api_key()
    second, _, _ = generate_api_key()
    assert first != second


def test_full_key_has_expected_prefix() -> None:
    full_key, _, _ = generate_api_key()
    assert full_key.startswith("lgw_")


def test_key_prefix_is_a_prefix_of_full_key_and_shorter() -> None:
    full_key, key_prefix, _ = generate_api_key()
    assert full_key.startswith(key_prefix)
    assert len(key_prefix) < len(full_key)


def test_hash_api_key_matches_generated_hash() -> None:
    full_key, _, key_hash = generate_api_key()
    assert hash_api_key(full_key) == key_hash


def test_hash_api_key_is_deterministic() -> None:
    assert hash_api_key("some-fixed-value") == hash_api_key("some-fixed-value")
