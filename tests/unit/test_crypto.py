from app.core.crypto import decrypt_secret, encrypt_secret


def test_secret_round_trip() -> None:
    value = "super-secret-api-value"
    encrypted = encrypt_secret(value)
    assert encrypted != value
    assert value not in encrypted
    assert decrypt_secret(encrypted) == value


def test_secret_uses_random_nonce() -> None:
    value = "same-secret"
    assert encrypt_secret(value) != encrypt_secret(value)
