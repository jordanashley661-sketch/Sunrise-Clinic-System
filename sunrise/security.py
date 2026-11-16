"""Salted password storage using Python's standard library."""

import hashlib
import hmac
import secrets

ITERATIONS = 600_000


def hash_password(password):
    """Return a versioned PBKDF2-SHA256 record; never store the password."""
    if not isinstance(password, str) or not 15 <= len(password) <= 128:
        raise ValueError("Use a passphrase between 15 and 128 characters.")
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), ITERATIONS
    )
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest.hex()}"


def verify_password(password, stored):
    """Verify without timing-sensitive equality; reject malformed records."""
    try:
        algorithm, rounds, salt, expected = stored.split("$")
        if algorithm != "pbkdf2_sha256" or not 1 <= int(rounds) <= 2_000_000:
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(rounds)
        ).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, AttributeError):
        return False
