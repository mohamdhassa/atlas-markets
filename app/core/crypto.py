from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings


def _key() -> bytes:
    return hashlib.sha256(get_settings().atlas_markets_master_key.encode()).digest()


def encrypt_secret(value: str) -> str:
    nonce = os.urandom(12)
    ciphertext = AESGCM(_key()).encrypt(nonce, value.encode(), b"atlas-markets-broker-credential")
    return base64.urlsafe_b64encode(nonce + ciphertext).decode()


def decrypt_secret(token: str) -> str:
    payload = base64.urlsafe_b64decode(token.encode())
    nonce, ciphertext = payload[:12], payload[12:]
    return AESGCM(_key()).decrypt(nonce, ciphertext, b"atlas-markets-broker-credential").decode()
