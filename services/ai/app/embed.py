from __future__ import annotations

import hashlib
import math
import re

"""
Query embedding.

**This must stay identical to services/pipeline/app/embed.py.** Cosine
similarity between vectors from two different models is a number that means
nothing, and nothing about the system would look broken if they drifted apart —
retrieval would keep ranking, answers would keep citing, and every result would
be subtly wrong.

The duplication is deliberate: the two services deploy separately and a shared
package would couple their release cycles. The drift is guarded at runtime
instead — `retrieval.search_within_video` compares the query's model id against
the one stored on the chunks and raises ModelMismatch rather than returning
plausible nonsense.
"""

DIMENSIONS = 1024
_TOKEN = re.compile(r"[a-z0-9']+")


def _l2_normalise(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    return vector if norm == 0 else [value / norm for value in vector]


class HashingEmbedder:
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
    model_id = "bge-m3"

    def __init__(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:  # pragma: no cover
            raise RuntimeError("bge-m3 needs sentence-transformers") from error
        self._model = SentenceTransformer("BAAI/bge-m3")

    def embed(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [list(map(float, vector)) for vector in vectors]


def build_embedder(prefer_real: bool):
    if prefer_real:
        try:
            return BgeM3Embedder()
        except RuntimeError:
            pass
    return HashingEmbedder()
