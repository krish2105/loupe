import uuid

import httpx
import jwt
import pytest
from asgi_lifespan import LifespanManager

from app.config import settings
from app.main import app
from app.passwords import WeakPassword, hash_password, verify_password

"""
The local identity provider.

The tests that matter are not "can someone sign in" — they are the ones about
this service refusing to be anything more than a development convenience, and
about the tokens it mints being indistinguishable from a hosted provider's.
"""

TEST_SECRET = "test-secret-not-used-anywhere-real"


@pytest.fixture(scope="session", autouse=True)
def secret():
    settings.supabase_jwt_secret = TEST_SECRET
    yield
    settings.supabase_jwt_secret = ""


@pytest.fixture
async def client():
    try:
        async with LifespanManager(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
                yield c
    except Exception as error:  # noqa: BLE001 — no database on this machine
        if "connect" in str(error).lower() or "refused" in str(error).lower():
            pytest.skip("No database available")
        raise


def new_email() -> str:
    return f"listener-{uuid.uuid4().hex[:10]}@example.com"


class TestItRefusesToBeDeployed:
    def test_it_will_not_start_outside_local(self, monkeypatch):
        """
        The single most important test here.

        §5.1 rejected a development auth bypass on the grounds that it is one
        misconfigured deploy away from being a production one. This service is a
        larger version of that risk, so it does not rely on nobody deploying it.
        """
        from app.main import _refuse_outside_development

        monkeypatch.setattr(settings, "environment", "production")

        with pytest.raises(RuntimeError, match="will not start"):
            _refuse_outside_development()

    def test_it_will_not_start_without_a_signing_secret(self, monkeypatch):
        # Without a matching secret every token it issued would be rejected by
        # the API, which is a confusing failure rather than an obvious one.
        from app.main import _refuse_outside_development

        monkeypatch.setattr(settings, "supabase_jwt_secret", "")

        with pytest.raises(RuntimeError, match="SUPABASE_JWT_SECRET"):
            _refuse_outside_development()


class TestTheTokens:
    async def test_a_token_carries_exactly_what_the_api_requires(self, client):
        """
        The core API decodes with audience="authenticated" and
        options={"require": ["exp", "sub"]}. A token missing any of those is
        rejected there, not here, which would be a confusing place to find out.
        """
        response = await client.post(
            "/auth/v1/signup", json={"email": new_email(), "password": "correct horse"}
        )
        assert response.status_code == 200

        claims = jwt.decode(
            response.json()["access_token"],
            TEST_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
            options={"require": ["exp", "sub"]},
        )

        assert claims["role"] == "authenticated"
        assert uuid.UUID(claims["sub"])

    async def test_a_token_signed_with_another_secret_is_not_accepted(self, client):
        forged = jwt.encode(
            {"sub": str(uuid.uuid4()), "aud": "authenticated", "exp": 9_999_999_999},
            "a different secret",
            algorithm="HS256",
        )

        response = await client.get(
            "/auth/v1/user", headers={"Authorization": f"Bearer {forged}"}
        )
        assert response.status_code == 401


class TestSigningUp:
    async def test_it_creates_the_profile_row_too(self, client):
        """
        users.handle is NOT NULL UNIQUE and every authenticated feature has a
        foreign key to users.id. A credential without a profile authenticates
        someone into a session where every write fails.
        """
        email = new_email()
        response = await client.post(
            "/auth/v1/signup", json={"email": email, "password": "correct horse"}
        )

        user_id = response.json()["user"]["id"]
        me = await client.get(
            "/auth/v1/user",
            headers={"Authorization": f"Bearer {response.json()['access_token']}"},
        )
        assert me.json()["id"] == user_id
        assert me.json()["email"] == email

    async def test_the_same_email_twice_is_refused(self, client):
        email = new_email()
        await client.post("/auth/v1/signup", json={"email": email, "password": "correct horse"})

        again = await client.post(
            "/auth/v1/signup", json={"email": email, "password": "another one"}
        )
        assert again.status_code == 422
        assert again.json()["detail"]["error_code"] == "user_already_exists"

    async def test_a_short_password_is_refused_in_gotrue_s_shape(self, client):
        # supabase-js surfaces `msg` to the caller and the login form renders it.
        response = await client.post(
            "/auth/v1/signup", json={"email": new_email(), "password": "short"}
        )

        assert response.status_code == 422
        assert response.json()["detail"]["error_code"] == "weak_password"


class TestSigningIn:
    async def test_the_password_grant_returns_a_session(self, client):
        email = new_email()
        await client.post("/auth/v1/signup", json={"email": email, "password": "correct horse"})

        response = await client.post(
            "/auth/v1/token?grant_type=password",
            json={"email": email, "password": "correct horse"},
        )

        assert response.status_code == 200
        assert response.json()["token_type"] == "bearer"
        assert response.json()["refresh_token"]

    async def test_a_wrong_password_and_an_unknown_account_answer_identically(
        self, client
    ):
        """
        Two different answers is an account-enumeration oracle: it tells anyone
        who asks which addresses have accounts here.
        """
        email = new_email()
        await client.post("/auth/v1/signup", json={"email": email, "password": "correct horse"})

        wrong = await client.post(
            "/auth/v1/token?grant_type=password",
            json={"email": email, "password": "not the password"},
        )
        unknown = await client.post(
            "/auth/v1/token?grant_type=password",
            json={"email": new_email(), "password": "not the password"},
        )

        assert wrong.status_code == unknown.status_code == 400
        assert wrong.json() == unknown.json()

    async def test_refresh_rotates_the_token(self, client):
        """A refresh token that never changes is a password with a longer name."""
        email = new_email()
        first = await client.post(
            "/auth/v1/signup", json={"email": email, "password": "correct horse"}
        )
        original = first.json()["refresh_token"]

        refreshed = await client.post(
            "/auth/v1/token?grant_type=refresh_token",
            json={"refresh_token": original},
        )

        assert refreshed.status_code == 200
        assert refreshed.json()["refresh_token"] != original

        # And the old one no longer works.
        replayed = await client.post(
            "/auth/v1/token?grant_type=refresh_token",
            json={"refresh_token": original},
        )
        assert replayed.status_code == 400


class TestPasswordHashing:
    def test_a_hash_carries_its_own_parameters(self):
        """
        A stored hash that does not describe itself cannot be verified after the
        work factor changes, which turns a routine increase into a forced
        password reset for everyone.
        """
        stored = hash_password("correct horse battery staple")

        scheme, cost, block, parallelism, salt, key = stored.split("$")
        assert scheme == "scrypt"
        assert int(cost) >= 2**14
        assert int(block) and int(parallelism)
        assert len(salt) == 32 and len(key) == 64

    def test_the_same_password_hashes_differently_every_time(self):
        assert hash_password("correct horse") != hash_password("correct horse")

    def test_verification_round_trips(self):
        stored = hash_password("correct horse")

        assert verify_password("correct horse", stored)
        assert not verify_password("Correct horse", stored)

    def test_a_corrupt_hash_fails_the_login_not_the_endpoint(self):
        assert not verify_password("anything", "not a hash at all")
        assert not verify_password("anything", "scrypt$oops")
        assert not verify_password("anything", "")

    def test_a_short_password_is_refused(self):
        with pytest.raises(WeakPassword):
            hash_password("short")
