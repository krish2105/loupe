from __future__ import annotations

from dataclasses import dataclass

"""
Retrieval — the half of the AI layer that is a measurement rather than a
generation.

§11.1: "Ask-video must refuse. A confident wrong answer about video content is
the failure mode that gets noticed in a demo. Threshold on retrieval score and
refuse below it. Track refusal rate as a headline metric — it is a feature, not
a defect."

So the threshold lives here, as a named constant with a stated rationale, and
the decision to refuse is made *before* anything is generated. A pipeline that
generates first and checks afterwards has already lost — the model will produce
something plausible from weak context, and plausible is exactly the problem.
"""

#: Cosine similarity below which retrieval is too weak to answer from.
#:
#: Deliberately conservative. The asymmetry matters: a refusal on a question
#: that was answerable is a mild disappointment, while a confident answer about
#: something the speaker never said discredits the whole intelligence layer.
#: This is a starting value to be tuned against the §11.2 eval set, not a
#: tuned one — recorded as such rather than presented as optimised.
REFUSAL_THRESHOLD = 0.42

#: How many chunks to retrieve before deciding.
CANDIDATES = 8

#: §11's contract: 1–4 citations.
MAX_CITATIONS = 4

#: Citations below this add noise rather than support.
CITATION_THRESHOLD = 0.34


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    video_id: str
    chunk_index: int
    start_sec: float
    end_sec: float
    text_display: str
    text_normalised: str
    similarity: float


class ModelMismatch(RuntimeError):
    """
    Raised when the query and the chunks were embedded by different models.

    This is the quiet catastrophe of a vector search: cosine similarity between
    vectors from two different models is a number, and it means nothing.
    Retrieval keeps working, results keep ranking, and every answer is subtly
    wrong with no error anywhere. Better to fail loudly.
    """


def to_pgvector(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.6f}" for value in vector) + "]"


def should_refuse(chunks: list[RetrievedChunk], threshold: float = REFUSAL_THRESHOLD) -> bool:
    """
    Refuse when nothing retrieved is close enough to the question.

    Judged on the best match, not the average: one strongly relevant passage is
    enough to answer from, and averaging would let a pile of weak matches
    outvote it in either direction.
    """
    if not chunks:
        return True
    return max(chunk.similarity for chunk in chunks) < threshold


def select_citations(
    chunks: list[RetrievedChunk],
    limit: int = MAX_CITATIONS,
    threshold: float = CITATION_THRESHOLD,
) -> list[RetrievedChunk]:
    """
    The passages worth pointing at.

    Deduplicated by proximity: two chunks overlapping by 50 tokens frequently
    both match, and citing the same moment twice makes the answer look padded.
    """
    strong = [chunk for chunk in chunks if chunk.similarity >= threshold]
    selected: list[RetrievedChunk] = []

    for chunk in sorted(strong, key=lambda c: c.similarity, reverse=True):
        if any(abs(chunk.start_sec - kept.start_sec) < 20.0 for kept in selected):
            continue
        selected.append(chunk)
        if len(selected) >= limit:
            break

    # Read in the order the talk says them, not in score order.
    return sorted(selected, key=lambda c: c.start_sec)


async def embedding_model_for(pool, video_id) -> str | None:
    """Which model embedded this video's chunks."""
    return await pool.fetchval(
        """
        SELECT embedding_model FROM transcript_chunks
        WHERE video_id = $1 AND embedding IS NOT NULL
        LIMIT 1
        """,
        video_id,
    )


async def search_within_video(
    pool, video_id, query_vector: list[float], query_model: str, limit: int = CANDIDATES
) -> list[RetrievedChunk]:
    """
    §11's ask-video contract: "this video's chunks only".

    The video filter is in the WHERE clause rather than applied afterwards.
    Retrieving globally and filtering would let another talk's passages consume
    the candidate budget and silently starve the one being asked about.
    """
    stored_model = await embedding_model_for(pool, video_id)
    if stored_model is None:
        return []
    if stored_model != query_model:
        raise ModelMismatch(
            f"chunks were embedded with {stored_model!r} but the query used "
            f"{query_model!r}; the similarity would be meaningless."
        )

    rows = await pool.fetch(
        """
        SELECT id, video_id, chunk_index, start_sec, end_sec,
               text_display, text_normalised,
               1 - (embedding <=> $2::vector) AS similarity
        FROM transcript_chunks
        WHERE video_id = $1 AND embedding IS NOT NULL
        ORDER BY embedding <=> $2::vector
        LIMIT $3
        """,
        video_id,
        to_pgvector(query_vector),
        limit,
    )

    return [_row_to_chunk(row) for row in rows]


async def search_across_catalogue(
    pool, query_vector: list[float], query_model: str, limit: int = 20
) -> list[RetrievedChunk]:
    """
    §11 semantic search: "Ranked videos, each with best-matching moment and
    start_sec."

    One row per video — DISTINCT ON keeps the best moment from each talk rather
    than letting one well-matched talk fill the whole page with its own chunks.
    """
    rows = await pool.fetch(
        """
        SELECT DISTINCT ON (c.video_id)
               c.id, c.video_id, c.chunk_index, c.start_sec, c.end_sec,
               c.text_display, c.text_normalised,
               1 - (c.embedding <=> $1::vector) AS similarity
        FROM transcript_chunks c
        JOIN videos v ON v.id = c.video_id
        WHERE c.embedding IS NOT NULL
          AND c.embedding_model = $2
          AND v.visibility = 'public'
        ORDER BY c.video_id, c.embedding <=> $1::vector
        """,
        to_pgvector(query_vector),
        query_model,
    )

    chunks = [_row_to_chunk(row) for row in rows]
    chunks.sort(key=lambda c: c.similarity, reverse=True)
    return chunks[:limit]


def _row_to_chunk(row) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=str(row["id"]),
        video_id=str(row["video_id"]),
        chunk_index=row["chunk_index"],
        start_sec=float(row["start_sec"]),
        end_sec=float(row["end_sec"]),
        text_display=row["text_display"],
        text_normalised=row["text_normalised"],
        similarity=float(row["similarity"]),
    )
