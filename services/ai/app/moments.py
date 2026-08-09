from __future__ import annotations

import re

"""
Turning a cited chunk into a cited moment.

§11.1 promises that a citation lets someone jump to the moment. What the
system actually returned was the *chunk's* start time, and a chunk is minutes
long — so "jump to the moment" landed at the top of a three-minute passage and
left the viewer to find the sentence themselves.

That was invisible until the evaluation stopped grading itself. The fixture
golden set read its expected timestamps from chunk boundaries, so it was
checking that a citation equals the chunk start, which is true by construction.
Anchoring expected timestamps on the sentence that actually answers the
question instead dropped citation accuracy to near zero, and the reason was
never retrieval — it was that a citation had no idea where inside its own
passage the answer was.

The word timings needed to fix it were already stored. §10.2 made word-level
timestamps a hard requirement precisely so this would be possible, and then
nothing read them.

Everything here is pure. Given a question, a passage, and the word timings, it
returns a number.
"""

#: Sentence-ish. Transcripts are punctuated by the recogniser rather than by a
#: writer, so this stays deliberately simple — splitting on terminal
#: punctuation followed by a capital gets it right often enough, and a
#: mis-split costs a few seconds of citation precision rather than a wrong
#: answer.
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

#: Words too common to carry meaning. Kept small on purpose: a long stop list
#: starts removing the terms that distinguish one talk from another.
_STOPWORDS = frozenset(
    """a an and are as at be by do does for from how in into is it its of on or
    that the their there these this to was what when where which who why with
    you your""".split()
)


def split_sentences(passage: str) -> list[str]:
    return [part.strip() for part in _SENTENCE.split(passage.strip()) if part.strip()]


def _content_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {word for word in words if word not in _STOPWORDS and len(word) > 2}


def best_sentence(question: str, sentences: list[str]) -> int:
    """
    Which sentence in the passage most likely answers the question.

    Lexical overlap rather than a second embedding pass. The passage has
    already been chosen by semantic retrieval, so the hard discrimination is
    done — this only has to pick among a handful of sentences that are all
    about the right subject, and overlap is enough for that. It also costs
    nothing, which matters on a free tier where every embedding call is metered.

    Normalised by sentence length so a long sentence does not win by containing
    more words in general. Ties, including a total absence of overlap, resolve
    to the first sentence, which is the current behaviour and a safe floor.
    """
    if not sentences:
        return 0

    asked = _content_words(question)
    if not asked:
        return 0

    best_index, best_score = 0, 0.0

    for index, sentence in enumerate(sentences):
        words = _content_words(sentence)
        if not words:
            continue
        overlap = len(asked & words)
        if not overlap:
            continue
        # Divided by the square root rather than the count: dividing by length
        # outright over-rewards three-word fragments that happen to match.
        score = overlap / (len(words) ** 0.5)
        if score > best_score:
            best_index, best_score = index, score

    return best_index


def locate(
    words: list[dict],
    phrase: str,
    window_start: float,
    window_end: float,
) -> float | None:
    """
    The start time of `phrase`, searched only within a window.

    Restricted to the window because talks repeat themselves — a speaker who
    says "the key value cache" six times would otherwise have every citation
    resolve to the first occurrence, which is worse than citing the chunk
    start. The window is the chunk the phrase came from, so the answer is the
    occurrence that was actually retrieved.

    Returns None when the phrase cannot be found, and the caller then keeps the
    chunk start. A slightly coarse citation beats a confidently wrong one.
    """
    target = [w for w in re.findall(r"[a-z0-9]+", phrase.lower()) if w]
    if not target:
        return None

    # Only the words inside the window, with their original timings.
    inside = [
        (index, re.sub(r"[^a-z0-9]", "", str(word.get("w", "")).lower()))
        for index, word in enumerate(words)
        if window_start - 0.5 <= float(word.get("s", -1)) <= window_end + 0.5
    ]
    if not inside:
        return None

    spoken = [text for _, text in inside]
    head = target[: min(6, len(target))]

    for position in range(len(spoken) - len(head) + 1):
        if spoken[position : position + len(head)] == head:
            original = inside[position][0]
            return round(float(words[original]["s"]), 2)

    return None


def best_sentence_by_vector(
    query_vector: list[float], sentence_vectors: list[list[float]]
) -> int:
    """
    Which sentence is closest to the question in embedding space.

    Lexical overlap picks a neighbouring sentence more often than not — measured
    on this corpus, nine of nineteen citations landed six to fourteen seconds
    out, which is one or two sentences. Sentences within one passage are all
    about the same subject and differ by shades that shared vocabulary does not
    capture; the embedding does.

    Vectors are compared by dot product rather than full cosine because bge-m3
    returns normalised vectors, so the norms are 1 and dividing by them is
    arithmetic with no effect.
    """
    if not sentence_vectors:
        return 0

    best_index, best_score = 0, float("-inf")
    for index, vector in enumerate(sentence_vectors):
        score = sum(a * b for a, b in zip(query_vector, vector, strict=False))
        if score > best_score:
            best_index, best_score = index, score

    return best_index


def moment_for(
    question: str,
    passage: str,
    words: list[dict],
    chunk_start: float,
    chunk_end: float,
    sentence_vectors: list[list[float]] | None = None,
    query_vector: list[float] | None = None,
) -> float:
    """
    Where inside its chunk a citation should point.

    Falls back to `chunk_start` whenever the sentence cannot be located, which
    is the behaviour this replaces — so this can make a citation better and
    cannot make it worse.
    """
    sentences = split_sentences(passage)
    if not sentences:
        return chunk_start

    if sentence_vectors and query_vector:
        index = best_sentence_by_vector(query_vector, sentence_vectors)
    else:
        index = best_sentence(question, sentences)

    chosen = sentences[min(index, len(sentences) - 1)]
    located = locate(words, chosen, chunk_start, chunk_end)

    return located if located is not None else chunk_start
