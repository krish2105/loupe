from __future__ import annotations

import secrets
import time
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import asyncpg
import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

from .config import settings
from .passwords import WeakPassword, hash_password, verify_password

"""
A local identity provider, speaking enough of GoTrue's API for the web app to
sign in against it unchanged.

Why this exists. Every authenticated feature in Loupe — comments, history,
playlists, downloads, notifications — has been written and tested server-side
and never once exercised from a browser, because doing so needs a hosted
Supabase project and this machine has no Docker to run one locally. Five phase
gates are partial for that single reason.

What it is not. It is not a second way to authenticate. It mints ordinary HS256
tokens with the same secret, the same `aud`, and the same claims the hosted
provider issues, and the core API verifies them through the code path it already
had. There is no bypass, no trusted header, and no branch in the API that knows
this service exists. Swapping in a real Supabase project means changing two
environment variables and deleting nothing.

Why it imitates GoTrue's HTTP shape rather than being simpler. The web app talks
to auth through `@supabase/ssr`, which owns cookie handling, session refresh and
storage. Reimplementing the client to talk to a simpler endpoint would mean the
development sign-in path and the production one were different code — and the
one that never runs is the one that breaks.

The guard below is the important part of this file.
"""


def _refuse_outside_development() -> None:
    """
    Fail closed, loudly, at startup.

    §5.1's auth module says it best: "A header that skips verification when
    ENVIRONMENT=local is one misconfigured deploy away from being an
    authentication bypass in production, and this repository is public." This
    service is a bigger version of that risk, so it does not rely on nobody
    deploying it. It refuses to start.
    """
    if settings.environment != "local":
        raise RuntimeError(
            "loupe-auth is a development identity provider and will not start "
            f"with ENVIRONMENT={settings.environment!r}. Use Supabase Auth, or "
            "any other GoTrue deployment, for anything that is not one "
            "developer's machine."
        )

    if not settings.supabase_jwt_secret:
        raise RuntimeError(
            "SUPABASE_JWT_SECRET is required. It must match the core API's, or "
            "every token this issues will be rejected."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _refuse_outside_development()

    dsn = settings.database_url.replace("postgres://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)

    # Created here rather than in db/migrations, because the migration chain is
    # what runs against production and this table must never reach it.
    async with pool.acquire() as connection:
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS dev_auth_identities (
              user_id       uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
              email         text NOT NULL UNIQUE,
              password_hash text NOT NULL,
              refresh_token text NOT NULL UNIQUE,
              created_at    timestamptz NOT NULL DEFAULT now()
            )
            """
        )

    app.state.pool = pool
    yield
    await pool.close()


app = FastAPI(title="Loupe development auth", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def pool() -> asyncpg.Pool:
    return app.state.pool


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class RefreshRequest(BaseModel):
    refresh_token: str = ""


def mint_access_token(user_id: UUID, email: str) -> str:
    """
    The same claim set a hosted GoTrue issues, minus what Loupe never reads.

    `aud`, `sub` and `exp` are the three the core API requires — it decodes with
    `options={"require": ["exp", "sub"]}` and `audience="authenticated"` — so
    those are not optional here. The rest is what supabase-js expects to find on
    a session user.
    """
    now = int(time.time())

    return jwt.encode(
        {
            "sub": str(user_id),
            "aud": "authenticated",
            "role": "authenticated",
            "email": email,
            "iat": now,
            "exp": now + settings.access_token_ttl_seconds,
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )


def serialise_user(user_id: UUID, email: str) -> dict:
    return {
        "id": str(user_id),
        "aud": "authenticated",
        "role": "authenticated",
        "email": email,
        "email_confirmed_at": "2026-01-01T00:00:00Z",
        "app_metadata": {"provider": "email", "providers": ["email"]},
        "user_metadata": {},
    }


def session_payload(user_id: UUID, email: str, refresh_token: str) -> dict:
    return {
        "access_token": mint_access_token(user_id, email),
        "token_type": "bearer",
        "expires_in": settings.access_token_ttl_seconds,
        "expires_at": int(time.time()) + settings.access_token_ttl_seconds,
        "refresh_token": refresh_token,
        "user": serialise_user(user_id, email),
    }


def handle_from(email: str) -> str:
    """
    A handle from the local part of the address, kept unique by a short suffix.

    `users.handle` is NOT NULL UNIQUE and the profile row has to exist before
    any foreign key to it will hold — comments, saves, playlists and downloads
    all reference it.
    """
    local = email.split("@", 1)[0]
    cleaned = "".join(character for character in local.lower() if character.isalnum())
    return f"{cleaned or 'listener'}-{secrets.token_hex(3)}"


@app.get("/health")
async def health() -> dict[str, object]:
    return {"status": "ok", "environment": settings.environment, "provider": "dev"}


@app.post("/auth/v1/signup")
async def signup(credentials: Credentials) -> dict:
    """
    Create an account.

    The profile row and the credential are written in one transaction. A
    credential whose user does not exist would authenticate someone into a
    session whose every foreign key fails, which is a worse state than a failed
    signup.
    """
    try:
        password_hash = hash_password(credentials.password)
    except WeakPassword as weak:
        # GoTrue's shape, because supabase-js surfaces `msg` to the caller and
        # the login form renders it.
        raise HTTPException(
            status_code=422, detail={"error_code": "weak_password", "msg": str(weak)}
        ) from weak

    email = credentials.email.lower()
    user_id = uuid4()
    refresh_token = secrets.token_urlsafe(32)

    async with pool().acquire() as connection:
        async with connection.transaction():
            existing = await connection.fetchval(
                "SELECT user_id FROM dev_auth_identities WHERE email = $1", email
            )
            if existing:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error_code": "user_already_exists",
                        "msg": "An account with this email already exists.",
                    },
                )

            await connection.execute(
                "INSERT INTO users (id, handle, display_name) VALUES ($1, $2, $3)",
                user_id,
                handle_from(email),
                email.split("@", 1)[0],
            )
            await connection.execute(
                """
                INSERT INTO dev_auth_identities
                    (user_id, email, password_hash, refresh_token)
                VALUES ($1, $2, $3, $4)
                """,
                user_id,
                email,
                password_hash,
                refresh_token,
            )

    return session_payload(user_id, email, refresh_token)


@app.post("/auth/v1/token")
async def token(
    payload: dict,
    grant_type: str = Query(default="password"),
) -> dict:
    """
    Both grants supabase-js uses: the password exchange and the refresh.

    A single endpoint switching on a query parameter, because that is GoTrue's
    shape and the client builds the request, not this service.
    """
    if grant_type == "refresh_token":
        return await _refresh(RefreshRequest(**payload).refresh_token)

    if grant_type != "password":
        raise HTTPException(
            status_code=400,
            detail={"error_code": "unsupported_grant_type", "msg": grant_type},
        )

    credentials = Credentials(**payload)
    email = credentials.email.lower()

    async with pool().acquire() as connection:
        row = await connection.fetchrow(
            """
            SELECT user_id, password_hash, refresh_token
            FROM dev_auth_identities WHERE email = $1
            """,
            email,
        )

    # One message for a missing account and a wrong password, and the hash is
    # verified either way. Two different answers, or two different response
    # times, is an account-enumeration oracle.
    stored = row["password_hash"] if row else _DUMMY_HASH
    if not verify_password(credentials.password, stored) or row is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "invalid_credentials",
                "msg": "Invalid login credentials",
            },
        )

    return session_payload(row["user_id"], email, row["refresh_token"])


async def _refresh(refresh_token: str) -> dict:
    if not refresh_token:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "invalid_grant", "msg": "Missing refresh token."},
        )

    rotated = secrets.token_urlsafe(32)

    async with pool().acquire() as connection:
        row = await connection.fetchrow(
            """
            UPDATE dev_auth_identities SET refresh_token = $2
            WHERE refresh_token = $1
            RETURNING user_id, email
            """,
            refresh_token,
            rotated,
        )

    if row is None:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "invalid_grant", "msg": "Invalid refresh token."},
        )

    # Rotated on use, like the real thing. A refresh token that never changes is
    # a password with a longer name.
    return session_payload(row["user_id"], row["email"], rotated)


async def require_token(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail={"msg": "No session."})

    try:
        return jwt.decode(
            authorization.split(" ", 1)[1],
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"require": ["exp", "sub"]},
        )
    except jwt.InvalidTokenError as invalid:
        raise HTTPException(status_code=401, detail={"msg": "Invalid session."}) from invalid


@app.get("/auth/v1/user")
async def current_user(claims: dict = Depends(require_token)) -> dict:
    """
    Who this token belongs to.

    The server-side `getUser()` call in the web app lands here, and it is the
    one that decides whether a page renders as signed in.
    """
    return serialise_user(UUID(claims["sub"]), claims.get("email", ""))


@app.post("/auth/v1/logout", status_code=204)
async def logout(claims: dict = Depends(require_token)) -> None:
    """
    Invalidate the refresh token.

    The access token stays valid until it expires, which is how bearer tokens
    work everywhere and is worth knowing rather than assuming otherwise.
    """
    async with pool().acquire() as connection:
        await connection.execute(
            "UPDATE dev_auth_identities SET refresh_token = $2 WHERE user_id = $1",
            UUID(claims["sub"]),
            secrets.token_urlsafe(32),
        )


#: Verified against when no account matches, so a login attempt for an unknown
#: address costs the same work as one for a known address.
_DUMMY_HASH = hash_password("this password matches nothing at all")
