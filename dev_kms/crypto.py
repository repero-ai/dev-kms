"""AES-256-GCM wrapping using cryptography's standard primitives."""

from __future__ import annotations

import base64
import binascii
import json
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

FORMAT_VERSION = 1


class CiphertextError(Exception):
    code = "invalid_ciphertext"


class UnsupportedFormatError(CiphertextError):
    code = "unsupported_format"


class KeyMismatchError(CiphertextError):
    code = "key_mismatch"


def new_wrapping_key() -> bytes:
    return os.urandom(32)


def generate_data_key(wrapping_key: bytes, key_id: str, key_version: int) -> tuple[bytes, str]:
    plaintext = os.urandom(32)
    nonce = os.urandom(12)
    ciphertext = AESGCM(wrapping_key).encrypt(nonce, plaintext, _aad(key_id, key_version))
    payload = {
        "v": FORMAT_VERSION,
        "kid": key_id,
        "kv": key_version,
        "n": _encode(nonce),
        "c": _encode(ciphertext),
    }
    return plaintext, _encode(json.dumps(payload, separators=(",", ":")).encode())


def unwrap_data_key(wrapping_key: bytes, key_id: str, key_version: int, value: str) -> bytes:
    try:
        payload = json.loads(_decode(value).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, CiphertextError) as error:
        raise CiphertextError() from error
    if not isinstance(payload, dict) or payload.get("v") != FORMAT_VERSION:
        raise UnsupportedFormatError()
    if payload.get("kid") != key_id:
        raise KeyMismatchError()
    if payload.get("kv") != key_version:
        raise CiphertextError()
    try:
        nonce = _decode(payload["n"])
        ciphertext = _decode(payload["c"])
    except (KeyError, TypeError, CiphertextError) as error:
        raise CiphertextError() from error
    if len(nonce) != 12:
        raise CiphertextError()
    try:
        return AESGCM(wrapping_key).decrypt(nonce, ciphertext, _aad(key_id, key_version))
    except InvalidTag as error:
        raise CiphertextError() from error


def _aad(key_id: str, key_version: int) -> bytes:
    return f"dev-kms:{key_id}:{key_version}".encode()


def _encode(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _decode(value: str) -> bytes:
    if not isinstance(value, str):
        raise CiphertextError()
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise CiphertextError() from error
