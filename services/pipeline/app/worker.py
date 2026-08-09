from __future__ import annotations

import json
import logging

from .asr import Transcriber
from .chapters import build_chapters, find_boundaries
from .chunk import Word, chunk_words
from .embed import Embedder
from .naming import HeuristicNamer
from .normalise import display, normalise

"""
The step implementations.

Each is a plain coroutine that either completes or raises. The stage machine
owns claiming, parking, retrying, and status — so nothing here has to think
about failure handling, and a step that raises for any reason lands the video
in the right place automatically.
"""

logger = logging.getLogger("pipeline")


async def transcribe(pool, video_id, transcriber: Transcriber) -> None:
    row = await pool.fetchrow(
        """
        SELECT v.duration_sec, a.hls_url
        FROM videos v LEFT JOIN video_assets a ON a.video_id = v.id
        WHERE v.id = $1
        """,
        video_id,
    )
    if row is None or not row["hls_url"]:
        raise RuntimeError("no playable asset to transcribe")

    words = transcriber.transcribe(row["hls_url"], row["duration_sec"] or 0)
    if not words:
        raise RuntimeError("transcription produced no words")

    full_text = display(" ".join(word.text for word in words))
    segments = [
        {"w": word.text, "s": word.start, "e": word.end, "spk": word.speaker}
        for word in words
    ]

    await pool.execute(
        """
        INSERT INTO transcripts
            (video_id, language, engine, engine_version, full_text, segments)
        VALUES ($1, 'en', $2, $3, $4, $5::jsonb)
        ON CONFLICT (video_id) DO UPDATE
        SET engine = EXCLUDED.engine,
            engine_version = EXCLUDED.engine_version,
            full_text = EXCLUDED.full_text,
            segments = EXCLUDED.segments
        """,
        video_id,
        transcriber.engine,
        transcriber.engine_version,
        full_text,
        json.dumps(segments),
    )


async def chunk(pool, video_id) -> None:
    row = await pool.fetchrow(
        "SELECT segments FROM transcripts WHERE video_id = $1", video_id
    )
    if row is None:
        raise RuntimeError("no transcript to chunk")

    raw = row["segments"]
    segments = json.loads(raw) if isinstance(raw, str) else raw
    words = [
        Word(text=item["w"], start=item["s"], end=item["e"], speaker=item.get("spk"))
        for item in segments
    ]

    chunks = chunk_words(words)
    if not chunks:
        raise RuntimeError("chunking produced nothing")

    # Re-chunking replaces rather than appends. A stale chunk with a valid
    # embedding is worse than no chunk: it stays retrievable and cites a
    # boundary that no longer exists.
    await pool.execute("DELETE FROM transcript_chunks WHERE video_id = $1", video_id)

    await pool.executemany(
        """
        INSERT INTO transcript_chunks
            (video_id, chunk_index, start_sec, end_sec, speaker,
             text_normalised, text_display, token_count)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        [
            (
                video_id,
                item.index,
                item.start_sec,
                item.end_sec,
                item.speaker,
                item.text_normalised,
                item.text_display,
                item.token_count,
            )
            for item in chunks
        ],
    )


async def embed(pool, video_id, embedder: Embedder) -> None:
    rows = await pool.fetch(
        """
        SELECT id, text_normalised FROM transcript_chunks
        WHERE video_id = $1 AND embedding IS NULL
        ORDER BY chunk_index
        """,
        video_id,
    )
    if not rows:
        # Already embedded. Not a failure — the step is resumable and this is
        # what a resumed run looks like.
        return

    vectors = embedder.embed([row["text_normalised"] for row in rows])

    await pool.executemany(
        """
        UPDATE transcript_chunks
        SET embedding = $2::vector, embedding_model = $3
        WHERE id = $1
        """,
        [
            (row["id"], "[" + ",".join(f"{v:.6f}" for v in vector) + "]", embedder.model_id)
            for row, vector in zip(rows, vectors, strict=True)
        ],
    )


async def enrich(pool, video_id) -> None:
    """
    Chapters. §11's failure mode is an unsegmented scrubber, so producing no
    chapters is a valid outcome rather than an error.
    """
    rows = await pool.fetch(
        """
        SELECT chunk_index, start_sec, end_sec, text_normalised, embedding
        FROM transcript_chunks
        WHERE video_id = $1 AND embedding IS NOT NULL
        ORDER BY chunk_index
        """,
        video_id,
    )
    if len(rows) < 5:
        logger.info("%s: too few chunks to detect chapters", video_id)
        return

    def parse(value) -> list[float]:
        if isinstance(value, str):
            return [float(part) for part in value.strip("[]").split(",")]
        return list(value)

    embeddings = [parse(row["embedding"]) for row in rows]
    starts = [float(row["start_sec"]) for row in rows]
    total = float(rows[-1]["end_sec"])

    boundaries = find_boundaries(embeddings, starts)
    if not boundaries:
        logger.info("%s: no topic shifts strong enough to be chapters", video_id)
        return

    namer = HeuristicNamer()
    corpus = " ".join(row["text_normalised"] for row in rows)

    # Name each span from the chunks it actually contains.
    edges = [0.0] + [b.start_sec for b in boundaries] + [total]
    titles = []
    for index in range(len(edges) - 1):
        span = " ".join(
            row["text_normalised"]
            for row in rows
            if edges[index] <= float(row["start_sec"]) < edges[index + 1]
        )
        titles.append(namer.title_for(span or corpus, corpus))

    chapters = build_chapters(boundaries, total, titles)

    await pool.execute("DELETE FROM chapters WHERE video_id = $1", video_id)
    await pool.executemany(
        """
        INSERT INTO chapters
            (video_id, chapter_index, start_sec, end_sec, title, confidence)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        [
            (video_id, c.index, c.start_sec, c.end_sec, c.title, c.confidence)
            for c in chapters
        ],
    )


__all__ = ["transcribe", "chunk", "embed", "enrich", "normalise"]
