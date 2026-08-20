from __future__ import annotations

import base64
import hashlib
import hmac
import os

from app.core.config import get_settings


def _key() -> bytes:
    return hashlib.sha256(get_settings().atlas_markets_master_key.encode()).digest()


def encrypt_secret(value: str) -> str:
    nonce = os.urandom(16)
    raw = value.encode()
    stream = hashlib.sha256(_key() + nonce).digest()
    encrypted = bytes(b ^ stream[i % len(stream)] for i, b in enumerate(raw))
    mac = hmac.new(_key(), nonce + encrypted, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(nonce + mac + encrypted).decode()


def decrypt_secret(token: str) -> str:
    payload = base64.urlsafe_b64decode(token.encode())
    nonce, mac, encrypted = payload[:16], payload[16:48], payload[48:]
    expected = hmac.new(_key(), nonce + encrypted, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected):
        raise ValueError("credential integrity check failed")
    stream = hashlib.sha256(_key() + nonce).digest()
    return bytes(b ^ stream[i % len(stream)] for i, b in enumerate(encrypted)).decode()
