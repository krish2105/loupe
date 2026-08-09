"""
S3 presigning, by hand.

Deliberately not boto3. The whole of what this service needs from S3 is a
query-string signature and two REST calls, and SigV4 presigning is a pure
function of its inputs — which makes it exactly the kind of thing the Bunny
integration next door already argues should be written out and tested against
known vectors rather than trusted. A signature that is subtly wrong fails as an
opaque 403 from an edge, usually only in production, and no stack trace ever
points at the line that caused it.

Writing it here also keeps the adapter honest about what it depends on. This
speaks plain S3, so the same code reaches Backblaze B2, Cloudflare R2, AWS or
MinIO by changing one endpoint. That is not hypothetical portability: B2 is the
current choice only because R2's signup would not take a card, and Oracle
halved its free tier in June without announcing it. The provider under this is
somebody else's decision to revise.

Path-style addressing, `SignedHeaders=host` — matching what B2's endpoint
actually accepts, verified against a signature produced by the AWS CLI.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from urllib.parse import quote, urlencode, urlsplit

ALGORITHM = "AWS4-HMAC-SHA256"

#: An unsigned payload for a presigned GET. The body is empty and the client
#: never sends one, so the hash of the empty string is the correct value.
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def _quote_key(key: str) -> str:
    """
    Percent-encode an object key for the canonical URI.

    `/` stays literal because it separates path segments; everything else that
    is not unreserved gets encoded. Getting this wrong is the single most common
    cause of a working signature over a simple key and a 403 over one containing
    a space — which HLS renditions and titles both produce eventually.
    """
    return quote(key, safe="/~")


def _signing_key(secret: str, date: str, region: str, service: str) -> bytes:
    key = f"AWS4{secret}".encode()
    for part in (date, region, service, "aws4_request"):
        key = hmac.new(key, part.encode(), hashlib.sha256).digest()
    return key


def presigned_url(
    *,
    endpoint: str,
    region: str,
    bucket: str,
    key: str,
    access_key: str,
    secret_key: str,
    expires_in: int,
    now: datetime,
    method: str = "GET",
) -> str:
    """
    A presigned URL valid for `expires_in` seconds.

    `now` is a parameter rather than a call to `utcnow()` so the result is
    reproducible: a signature that cannot be recomputed cannot be tested, and
    every test below pins a timestamp to compare against a fixed expectation.

    Callers pass an aware UTC datetime. A naive one would silently sign in local
    time and produce URLs that are already expired, or not yet valid, depending
    on which side of UTC the machine sits — a failure that looks like a clock
    problem on the server and is not.
    """
    if now.tzinfo is None:
        raise ValueError(
            "now must be timezone-aware; a naive datetime signs in local time "
            "and produces URLs that expire at the wrong moment."
        )

    stamp = now.astimezone(UTC)
    amz_date = stamp.strftime("%Y%m%dT%H%M%SZ")
    date = stamp.strftime("%Y%m%d")

    host = urlsplit(endpoint).netloc or endpoint
    scope = f"{date}/{region}/s3/aws4_request"
    canonical_uri = f"/{bucket}/{_quote_key(key.lstrip('/'))}"

    query = {
        "X-Amz-Algorithm": ALGORITHM,
        "X-Amz-Credential": f"{access_key}/{scope}",
        "X-Amz-Date": amz_date,
        "X-Amz-Expires": str(expires_in),
        "X-Amz-SignedHeaders": "host",
    }
    # SigV4 requires the query string sorted by key, and `urlencode` preserves
    # insertion order rather than sorting, so the sort is explicit.
    canonical_query = urlencode(sorted(query.items()), quote_via=quote, safe="~")

    canonical_request = "\n".join(
        [
            method,
            canonical_uri,
            canonical_query,
            f"host:{host}\n",
            "host",
            "UNSIGNED-PAYLOAD",
        ]
    )

    to_sign = "\n".join(
        [
            ALGORITHM,
            amz_date,
            scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ]
    )

    signature = hmac.new(
        _signing_key(secret_key, date, region, "s3"),
        to_sign.encode(),
        hashlib.sha256,
    ).hexdigest()

    return (
        f"{endpoint.rstrip('/')}{canonical_uri}"
        f"?{canonical_query}&X-Amz-Signature={signature}"
    )


def hls_key(video_id: str, *parts: str) -> str:
    """
    Where a video's HLS output lives in the bucket.

    One prefix per video, so a takedown is a prefix delete rather than a hunt
    for every rendition — which matters now that the platform accepts uploads
    from anyone and owes a removal path that actually removes things.
    """
    tail = "/".join(part.strip("/") for part in parts if part)
    return f"videos/{video_id}/hls" + (f"/{tail}" if tail else "")
