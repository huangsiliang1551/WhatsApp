"""
AIP-001: Fernet symmetric encryption for API key storage.

Uses AI_CONFIG_ENCRY_KEY from env. If unset, auto-generates key with a WARNING.
"""

import base64
import logging
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

_ENV_KEY_NAME = "AI_CONFIG_ENCRY_KEY"
_SALT = b"whatsapp-ai-provider-salt-v1"


def _derive_key(master_key: str) -> bytes:
    """Derive a 32-byte Fernet-compatible key from a master key string using PBKDF2."""
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=_SALT, iterations=600000)
    return base64.urlsafe_b64encode(kdf.derive(master_key.encode("utf-8")))


def get_encryption_key() -> bytes:
    """Get the Fernet encryption key from environment or auto-generate a stable one.

    The env var AI_CONFIG_ENCRY_KEY is used as the master secret.
    If unset, a warning is logged and a development-only key is derived from a fixed fallback.
    WARNING: The fallback is NOT secure for production! Set AI_CONFIG_ENCRY_KEY in production.
    """
    env_key = os.environ.get(_ENV_KEY_NAME)
    if env_key:
        return _derive_key(env_key)
    logger.warning(
        "AI_CONFIG_ENCRY_KEY not set. Using development-only fallback key. "
        "Set AI_CONFIG_ENCRY_KEY in production for secure API key storage."
    )
    return _derive_key("dev-only-fallback-do-not-use-in-production")


_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(get_encryption_key())
    return _fernet


def encrypt_key(plaintext: str) -> str:
    """Encrypt a plaintext API key and return a base64-encoded ciphertext string."""
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_key(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext back to the plaintext API key."""
    if not ciphertext:
        return ""
    return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
