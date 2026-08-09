import uuid

import pytest
from fastapi import HTTPException

from app import db

from .conftest import token_for


def auth(user_id) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_for(user_id)}"}


class TestAuthentication:
    async def test_a_write_without_a_token_is_rejected(self, client):
        response = await client.post(
            "/v1/watch-events",
            json={"video_id": str(uuid.uuid4()), "position_sec": 10, "watch_pct": 0.1},
        )
        assert response.status_code == 401

    async def test_an_expired_token_is_rejected(self, client):
        user_id = uuid.uuid4()
        response = await client.post(
            "/v1/watch-events",
            headers={"Authorization": f"Bearer {token_for(user_id, expired=True)}"},
            json={"video_id": str(uuid.uuid4()), "position_sec": 10, "watch_pct": 0.1},
        )
        assert response.status_code == 401

    async def test_a_token_signed_with_the_wrong_key_is_rejected(self, client):
        import jwt

        forged = jwt.encode(
            {"sub": str(uuid.uuid4()), "aud": "authenticated", "exp": 9999999999},
            "attacker-chosen-secret",
            algorithm="HS256",
        )
        response = await client.post(
            "/v1/watch-events",
            headers={"Authorization": f"Bearer {forged}"},
            json={"video_id": str(uuid.uuid4()), "position_sec": 10, "watch_pct": 0.1},
        )
        assert response.status_code == 401


class TestRecording:
    async def test_an_event_is_appended(self, client, seeded):
        response = await client.post(
            "/v1/watch-events",
            headers=auth(seeded["user_id"]),
            json={
                "video_id": str(seeded["video_id"]),
                "position_sec": 142,
                "watch_pct": 0.04,
            },
        )

        assert response.status_code == 204

        async with db.pool().acquire() as connection:
            count = await connection.fetchval(
                "SELECT count(*) FROM watch_events WHERE user_id = $1",
                seeded["user_id"],
            )
        assert count == 1

    async def test_repeated_writes_append_rather_than_overwrite(self, client, seeded):
        """
        §6.5 is the whole reason this table is shaped as it is: every position
        write is a new row, so the history survives and stays trainable.
        """
        for position in (10, 20, 30):
            await client.post(
                "/v1/watch-events",
                headers=auth(seeded["user_id"]),
                json={
                    "video_id": str(seeded["video_id"]),
                    "position_sec": position,
                    "watch_pct": position / 3600,
                },
            )

        async with db.pool().acquire() as connection:
            rows = await connection.fetch(
                "SELECT position_sec FROM watch_events WHERE user_id = $1 ORDER BY id",
                seeded["user_id"],
            )

        assert [row["position_sec"] for row in rows] == [10, 20, 30]

    async def test_an_unknown_video_is_a_client_error(self, client, seeded):
        response = await client.post(
            "/v1/watch-events",
            headers=auth(seeded["user_id"]),
            json={
                "video_id": str(uuid.uuid4()),
                "position_sec": 10,
                "watch_pct": 0.1,
            },
        )
        assert response.status_code == 404

    async def test_an_out_of_range_percentage_is_refused(self, client, seeded):
        response = await client.post(
            "/v1/watch-events",
            headers=auth(seeded["user_id"]),
            json={
                "video_id": str(seeded["video_id"]),
                "position_sec": 10,
                "watch_pct": 1.5,
            },
        )
        assert response.status_code == 422


class TestResume:
    async def test_nothing_to_resume_when_there_is_no_history(self, client, seeded):
        response = await client.get(
            f"/v1/videos/{seeded['video_id']}/resume",
            headers=auth(seeded["user_id"]),
        )

        assert response.status_code == 200
        assert response.json()["position_sec"] is None

    async def test_the_most_recent_position_is_returned(self, client, seeded):
        for position in (30, 900, 1400):
            await client.post(
                "/v1/watch-events",
                headers=auth(seeded["user_id"]),
                json={
                    "video_id": str(seeded["video_id"]),
                    "position_sec": position,
                    "watch_pct": position / 3600,
                },
            )

        response = await client.get(
            f"/v1/videos/{seeded['video_id']}/resume",
            headers=auth(seeded["user_id"]),
        )

        # A read-side aggregate over the append-only log, not a stored column.
        assert response.json()["position_sec"] == 1400

    async def test_a_barely_started_talk_is_not_offered(self, client, seeded):
        """§9.1 sets the floor at ten seconds — a prompt at four is noise."""
        await client.post(
            "/v1/watch-events",
            headers=auth(seeded["user_id"]),
            json={
                "video_id": str(seeded["video_id"]),
                "position_sec": 4,
                "watch_pct": 0.001,
            },
        )

        response = await client.get(
            f"/v1/videos/{seeded['video_id']}/resume",
            headers=auth(seeded["user_id"]),
        )
        assert response.json()["position_sec"] is None

    async def test_an_almost_finished_talk_is_not_offered(self, client, seeded):
        await client.post(
            "/v1/watch-events",
            headers=auth(seeded["user_id"]),
            json={
                "video_id": str(seeded["video_id"]),
                "position_sec": 3500,
                "watch_pct": 0.97,
            },
        )

        response = await client.get(
            f"/v1/videos/{seeded['video_id']}/resume",
            headers=auth(seeded["user_id"]),
        )
        assert response.json()["position_sec"] is None

    async def test_one_persons_history_is_never_offered_to_another(
        self, client, seeded
    ):
        await client.post(
            "/v1/watch-events",
            headers=auth(seeded["user_id"]),
            json={
                "video_id": str(seeded["video_id"]),
                "position_sec": 600,
                "watch_pct": 0.17,
            },
        )

        stranger = uuid.uuid4()
        response = await client.get(
            f"/v1/videos/{seeded['video_id']}/resume",
            headers=auth(stranger),
        )

        assert response.json()["position_sec"] is None


class TestAsymmetricTokens:
    """
    ES256 verification (Supabase JWT signing keys).

    A project created today signs access tokens asymmetrically, so the API has
    to verify against the project's public JWKS. Before this, every real login
    produced a token the API rejected with 401 and no clue why.
    """

    def _keypair(self):
        from cryptography.hazmat.primitives.asymmetric import ec

        private = ec.generate_private_key(ec.SECP256R1())
        return private, private.public_key()

    def test_a_valid_es256_token_is_accepted(self, monkeypatch):
        import time
        import uuid

        import jwt as pyjwt

        from app import auth

        private, public = self._keypair()
        user_id = uuid.uuid4()

        token = pyjwt.encode(
            {
                "sub": str(user_id),
                "aud": "authenticated",
                "exp": int(time.time()) + 3600,
            },
            private,
            algorithm="ES256",
        )

        class FakeKey:
            key = public

        class FakeJWKS:
            def get_signing_key_from_jwt(self, _token):
                return FakeKey()

        monkeypatch.setattr(auth, "_jwks", lambda: FakeJWKS())

        assert auth._decode(token)["sub"] == str(user_id)

    def test_a_public_key_cannot_be_used_as_an_hmac_secret(self, monkeypatch):
        """
        The classic JWT confusion attack: take the public key out of the JWKS,
        sign an HS256 token with it, and hope the server picks its verification
        key from the token's own `alg`.

        The token is assembled by hand because PyJWT refuses to build it —
        which protects this project's own code and not an attacker's, so the
        attack has to be reproduced rather than imported.

        It fails because the two verification paths never share key material.
        An HS256 token is only ever checked against the configured shared
        secret, which is not the public key.
        """
        import base64
        import hashlib
        import hmac
        import json
        import time
        import uuid

        from cryptography.hazmat.primitives import serialization

        from app import auth
        from app.config import settings

        _, public = self._keypair()
        public_pem = public.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        def b64(raw: bytes) -> bytes:
            return base64.urlsafe_b64encode(raw).rstrip(b"=")

        header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        payload = b64(
            json.dumps(
                {
                    "sub": str(uuid.uuid4()),
                    "aud": "authenticated",
                    "exp": int(time.time()) + 3600,
                }
            ).encode()
        )
        signing_input = header + b"." + payload
        signature = b64(hmac.new(public_pem, signing_input, hashlib.sha256).digest())
        forged = (signing_input + b"." + signature).decode()

        from tests.conftest import TEST_JWT_SECRET

        monkeypatch.setattr(settings, "supabase_jwt_secret", TEST_JWT_SECRET)

        with pytest.raises(HTTPException) as raised:
            auth._decode(forged)
        assert raised.value.status_code == 401

    def test_the_none_algorithm_is_refused(self):
        """
        An unsigned token. Also assembled by hand: PyJWT will not encode with
        `none` either, for the same reason.
        """
        import base64
        import json
        import time
        import uuid

        from app import auth

        def b64(raw: bytes) -> bytes:
            return base64.urlsafe_b64encode(raw).rstrip(b"=")

        header = b64(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        payload = b64(
            json.dumps(
                {
                    "sub": str(uuid.uuid4()),
                    "aud": "authenticated",
                    "exp": int(time.time()) + 3600,
                }
            ).encode()
        )
        unsigned = (header + b"." + payload + b".").decode()

        with pytest.raises(HTTPException) as raised:
            auth._decode(unsigned)
        assert raised.value.status_code == 401
