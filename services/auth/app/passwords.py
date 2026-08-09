from __future__ import annotations

import hmac
import os
from hashlib import scrypt

"""
Password hashing.

scrypt from the standard library rather than bcrypt or argon2 from a package.
Not because it is better — argon2id would be the choice for a real deployment —
but because this service exists so a developer can sign in on their own machine,
and adding a compiled dependency to reach that is the wrong trade.

The parameters are scrypt's interactive-login defaults. They are stated here
rather than left implicit, because "what work factor is this" is the first
question anyone reviewing a password hash should be able to answer.
"""

#: CPU/memory cost. 2^14 is the widely used interactive-login figure.
COST = 2**14
BLOCK_SIZE = 8
PARALLELISM = 1
SALT_BYTES = 16
KEY_BYTES = 32

#: A password shorter than this is refused. GoTrue's own default, so moving to a
#: hosted provider later does not suddenly reject accounts this one accepted.
MIN_LENGTH = 6


class WeakPassword(ValueError):
    pass


def hash_password(password: str) -> str:
    """
    Returns `scrypt$<cost>$<block>$<parallelism>$<salt>$<key>`, all hex.

    Self-describing on purpose. A stored hash that does not carry its own
    parameters cannot be verified after those parameters change, which turns a
    routine work-factor increase into a forced password reset for everyone.
    """
    if len(password) < MIN_LENGTH:
        raise WeakPassword(f"Password must be at least {MIN_LENGTH} characters.")

    salt = os.urandom(SALT_BYTES)
    key = _derive(password, salt, COST, BLOCK_SIZE, PARALLELISM)

    return "$".join(
        ["scrypt", str(COST), str(BLOCK_SIZE), str(PARALLELISM), salt.hex(), key.hex()]
    )


def verify_password(password: str, stored: str) -> bool:
    """
    Constant-time comparison against a stored hash.

    Returns False on anything malformed rather than raising. A corrupted row
    should fail the login, not the endpoint — and it must fail it in the same
    time and the same way as a wrong password, or the difference is a signal.
    """
    try:
        scheme, cost, block, parallelism, salt_hex, key_hex = stored.split("$")
        if scheme != "scrypt":
            return False

        expected = bytes.fromhex(key_hex)
        actual = _derive(
            password, bytes.fromhex(salt_hex), int(cost), int(block), int(parallelism)
        )
    except (ValueError, TypeError):
        return False

    return hmac.compare_digest(expected, actual)


def _derive(password: str, salt: bytes, cost: int, block: int, parallelism: int) -> bytes:
    return scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=cost,
        r=block,
        p=parallelism,
        dklen=KEY_BYTES,
        # scrypt's memory use is roughly 128 * n * r * p bytes, and Python
        # enforces a limit well below what these parameters need. Raised
        # explicitly rather than by lowering the work factor to fit.
        maxmem=256 * 1024 * 1024,
    )
