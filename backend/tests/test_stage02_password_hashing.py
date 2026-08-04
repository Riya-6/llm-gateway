from app.domains.auth.security import hash_password, verify_password


def test_hash_differs_from_plaintext() -> None:
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"


def test_verify_password_accepts_correct_password() -> None:
    hashed = hash_password("s3cr3t-password")
    assert verify_password("s3cr3t-password", hashed) is True


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("s3cr3t-password")
    assert verify_password("wrong-password", hashed) is False


def test_hashing_same_password_twice_produces_different_hashes() -> None:
    first = hash_password("same-password")
    second = hash_password("same-password")
    assert first != second
    assert verify_password("same-password", first) is True
    assert verify_password("same-password", second) is True
