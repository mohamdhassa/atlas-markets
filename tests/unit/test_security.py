from app.core.security import generate_session_token, hash_password, hash_session_token, verify_password


def test_password_hash_round_trip() -> None:
    encoded = hash_password("correct horse battery staple")
    assert encoded != "correct horse battery staple"
    assert verify_password("correct horse battery staple", encoded) is True
    assert verify_password("wrong password", encoded) is False


def test_password_hash_uses_unique_salt() -> None:
    first = hash_password("same password")
    second = hash_password("same password")
    assert first != second


def test_session_tokens_are_random_and_stored_as_hashes() -> None:
    first = generate_session_token()
    second = generate_session_token()
    assert first != second
    digest = hash_session_token(first, "test-secret")
    assert first not in digest
    assert len(digest) == 64
