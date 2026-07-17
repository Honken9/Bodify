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


def sniff_image(content: bytes) -> str | None:
    """Avgör bildformat ur filens magiska bytes — Content-Type-headern
    kan förfalskas och får inte styra vad som lagras eller serveras.

    Returnerar MIME-typ för JPEG/PNG/WebP, annars None."""
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if content[4:8] == b"ftyp" and content[8:12] in (
        b"heic", b"heix", b"hevc", b"mif1", b"msf1",
    ):
        return "image/heic"
    return None
