import hashlib
import secrets
from functools import lru_cache

from cryptography.fernet import Fernet

from smikhub.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    return Fernet(get_settings().fernet_key.encode())


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def generate_integration_token() -> str:
    return secrets.token_urlsafe(32)
