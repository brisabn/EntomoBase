from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()

HASH_PREFIX = "$argon2"
MIN_PASSWORD_LENGTH = 8

# hash of an arbitrary password; used to spend the same time when the email does not exist
_DUMMY_HASH = _hasher.hash("password-nobody-uses")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def is_hash(value: str) -> bool:
    return (value or "").startswith(HASH_PREFIX)


def verify_password(password: str, stored_hash: str | None) -> bool:
    if not stored_hash or not is_hash(stored_hash):
        # unknown user: spend the same time as a real check, so the response time
        # does not reveal whether the email exists, and always refuse
        try:
            _hasher.verify(_DUMMY_HASH, password)
        except (VerificationError, InvalidHashError):
            pass
        return False
    try:
        return _hasher.verify(stored_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)
