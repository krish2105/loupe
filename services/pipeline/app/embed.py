from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

"""
Embeddings — §10.2.

    "Pin the model version in the row. Models will change; stale rows must be
     identifiable."

Two implementations. `BgeM3Embedder` is the real one from §5.2 — multilingual,
open-weight, no per-call cost. `HashingEmbedder` is a lexical fallback used when
the model is not installed.

The fallback is a hashing vectoriser, not random noise. That distinction
matters: texts sharing vocabulary get similar vectors, so chapter detection
finds real boundaries and semantic search returns defensible neighbours. It is
weaker than a trained model — it has no idea that "GPU" and "accelerator" are
related — but it is a real technique with real behaviour, and its rows are
labelled `hashing-v1` so they are identifiable and re-indexable later.
"""

DIMENSIONS = 1024

_TOKEN = re.compile(r"[a-z0-9']+")


class Embedder(Protocol):
    model_id: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _l2_normalise(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


class HashingEmbedder:
    """
    Deterministic lexical embedding.

    Bigrams as well as unigrams, so word order carries a little signal — "cache
    the key values" and "values key the cache" should not be identical.
    """

    model_id = "hashing-v1"

    def __init__(self, dimensions: int = DIMENSIONS) -> None:
        self.dimensions = dimensions

    def _bucket(self, term: str) -> int:
        digest = hashlib.blake2b(term.encode(), digest_size=8).digest()
        return int.from_bytes(digest, "big") % self.dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            tokens = _TOKEN.findall(text.lower())
            vector = [0.0] * self.dimensions

            for token in tokens:
                vector[self._bucket(token)] += 1.0
            for first, second in zip(tokens, tokens[1:], strict=False):
                vector[self._bucket(f"{first}_{second}")] += 0.5

            vectors.append(_l2_normalise(vector))
        return vectors


class BgeM3Embedder:
    """
    The real embedder (§5.2): bge-m3, multilingual, open-weight.

    Imported lazily so the worker starts without torch installed — a machine
    that only needs to run the chunker should not need a gigabyte of wheels.
    """

    model_id = "bge-m3"

    def __init__(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:  # pragma: no cover - depends on install
            raise RuntimeError(
                "bge-m3 needs sentence-transformers. Install it, or the worker "
                "falls back to the hashing embedder."
            ) from error

        self._model = SentenceTransformer("BAAI/bge-m3")

    def embed(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [list(map(float, vector)) for vector in vectors]


def build_embedder(prefer_real: bool) -> Embedder:
    if prefer_real:
        try:
            return BgeM3Embedder()
        except RuntimeError:
            pass
    return HashingEmbedder()
