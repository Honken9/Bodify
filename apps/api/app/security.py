"""Kryptering av OAuth-tokens i vila (Fernet, nyckel härledd ur SECRET_KEY)."""

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet

from app.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    key = hashlib.sha256(get_settings().secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()


def hash_token(token: str) -> str:
    """SHA-256-hash för ingest-tokens — själva tokenen lagras aldrig."""
    return hashlib.sha256(token.encode()).hexdigest()
