from __future__ import annotations

from uuid import UUID

import jwt
from fastapi import Header, HTTPException
from jwt import PyJWKClient

from .config import settings

"""
Caller identity, from the access token.

Two issuers, two signatures, and that is not a compromise — it is what Supabase
did to its own tokens.

    ES256, asymmetric   a Supabase project with JWT signing keys. Verified
                        against the project's public JWKS. This is what a
                        project created today issues.

    HS256, shared key   a project still on the legacy JWT secret, and the
                        development identity provider in services/auth
                        (ADR 0004), which mints tokens in the same shape.

The path is chosen by the token's own `alg`, which sounds like the setup for the
classic JWT confusion attack and is not, because the two paths never share key
material. An HS256 token is only ever checked against the shared secret, which
an attacker does not have. An ES256 token is only ever checked against the JWKS
public key, which cannot sign anything. The attack that matters — presenting an
HS256 token signed with a public key lifted from the JWKS — fails because that
public key is never used as an HMAC secret.

`none` is not in either list.

There is deliberately no development bypass. A header that skips verification
when ENVIRONMENT=local is one misconfigured deploy away from being an
authentication bypass in production, and this repository is public. Tests mint a
real token with a test secret and travel the same code path.
"""

#: Never `none`, and never a family the corresponding key cannot produce.
SYMMETRIC = ["HS256"]
ASYMMETRIC = ["ES256", "RS256"]

_jwks_client: PyJWKClient | None = None


def _jwks() -> PyJWKClient:
    """
    The project's public signing keys.

    Cached by PyJWKClient, so a token verified twice costs one fetch. Supabase
    rotates by publishing a standby key alongside the current one, so a cache
    that refreshes on an unknown `kid` — which this does — survives a rotation
    without a deploy.
    """
    global _jwks_client

    if _jwks_client is None:
        if not settings.supabase_url:
            raise HTTPException(
                status_code=503,
                detail=(
                    "This token is signed with an asymmetric key, which needs "
                    "SUPABASE_URL set to verify against the project's JWKS."
                ),
            )
        _jwks_client = PyJWKClient(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json",
            cache_keys=True,
        )

    return _jwks_client


def _decode(token: str) -> dict:
    try:
        algorithm = jwt.get_unverified_header(token).get("alg", "")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session token.") from None

    if algorithm in ASYMMETRIC:
        try:
            key = _jwks().get_signing_key_from_jwt(token).key
        except HTTPException:
            raise
        except Exception:
            # A key that is not in the JWKS, or a JWKS that cannot be fetched.
            # Both are "this token is not one of ours" from here.
            raise HTTPException(
                status_code=401, detail="Invalid session token."
            ) from None

        return _verify(token, key, ASYMMETRIC)

    if not settings.supabase_jwt_secret:
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured. Set SUPABASE_JWT_SECRET.",
        )

    return _verify(token, settings.supabase_jwt_secret, SYMMETRIC)


def _verify(token: str, key: object, algorithms: list[str]) -> dict:
    try:
        return jwt.decode(
            token,
            key,  # type: ignore[arg-type]
            algorithms=algorithms,
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
