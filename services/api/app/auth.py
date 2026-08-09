from __future__ import annotations

from uuid import UUID

import jwt
from fastapi import Header, HTTPException

from .config import settings

"""
Caller identity, from the Supabase access token.

Supabase signs its access tokens with the project's JWT secret, so verifying
one needs no network call — which matters, because history is written on a
ten-second cadence and a round-trip per write would be absurd.

There is deliberately no development bypass. A header that skips verification
when ENVIRONMENT=local is one misconfigured deploy away from being an
authentication bypass in production, and this repository is public. Tests mint
a real token with a test secret and travel the same code path.
"""


def _decode(token: str) -> dict:
    if not settings.supabase_jwt_secret:
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured. Set SUPABASE_JWT_SECRET.",
        )

    try:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            # Supabase issues tokens with aud=authenticated.
            audience="authenticated",
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401, detail="Session expired. Sign in again."
        ) from None
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session token.") from None


async def require_user_id(authorization: str | None = Header(default=None)) -> UUID:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sign in to continue.")

    claims = _decode(authorization.split(" ", 1)[1])

    try:
        return UUID(claims["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid session token.") from None
