from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .retrieval import RetrievedChunk, select_citations, should_refuse

"""
Answering — §11's ask-video contract.

    Input:  question plus this video's chunks only
    Output: answer plus 1–4 citations with start_sec; explicit "not covered in
            this video" when retrieval is weak
    Failure: return the refusal, never a guess

Two answerers behind one interface.

`ExtractiveAnswerer` builds the answer from the retrieved passages themselves.
It is not a placeholder for a model — it has a property no generative answerer
has, which is that it cannot state anything the speaker did not say. Every word
of the answer is quoted transcript. That makes it a legitimate baseline, and it
is what the §11.2 eval set should measure a generative answerer *against*.

`GeneratedAnswerer` routes to a model when one is configured. §5 puts all
prompts and model routing in this service, which is why the prompt lives here
and nowhere else.
"""

REFUSAL_TEXT = (
    "That is not covered in this talk. The speaker does not discuss it in a way "
    "the transcript captures."
)


@dataclass(frozen=True)
class Answer:
    text: str
    citations: list[RetrievedChunk]
    refused: bool
    top_score: float
    model: str


class Answerer(Protocol):
    model: str

    async def answer(self, question: str, chunks: list[RetrievedChunk]) -> Answer: ...


def refusal(chunks: list[RetrievedChunk], model: str) -> Answer:
    """
    §11.1: the refusal is the product working, not failing.

    It carries no citations on purpose — the database rejects a refusal that
    has any, so an answer that hedged by refusing *and* pointing somewhere
    would not persist.
    """
    return Answer(
        text=REFUSAL_TEXT,
        citations=[],
        refused=True,
        top_score=max((chunk.similarity for chunk in chunks), default=0.0),
        model=model,
    )


class ExtractiveAnswerer:
    """Answers only in the speaker's own words."""

    model = "extractive-v1"

    async def answer(self, question: str, chunks: list[RetrievedChunk]) -> Answer:
        if should_refuse(chunks):
            return refusal(chunks, self.model)

        citations = select_citations(chunks)
        if not citations:
            return refusal(chunks, self.model)

        # Framed as quotation rather than as the product's own voice, because
        # that is exactly what it is.
        body = "\n\n".join(f"“{chunk.text_display.strip()}”" for chunk in citations)
        lead = (
            "Here is what the speaker says about that, in their own words:"
            if len(citations) > 1
            else "The speaker puts it this way:"
        )

        return Answer(
            text=f"{lead}\n\n{body}",
            citations=citations,
            refused=False,
            top_score=max(chunk.similarity for chunk in chunks),
            model=self.model,
        )


PROMPT = """You are answering a question about one recorded talk.

Use only the numbered passages below. They are the only thing you know about
this talk. If they do not answer the question, reply with exactly:
NOT_COVERED

Do not use outside knowledge. Do not speculate about what the speaker probably
meant. Quote or closely paraphrase, and keep it to three sentences.

Question: {question}

Passages:
{passages}
"""


class GeneratedAnswerer:  # pragma: no cover - requires a key
    """
    Model-backed answering. §5.2 selects Gemini Flash with a Groq fallback.

    The refusal decision is still made from the retrieval score *before* the
    model is called, and the prompt gives the model a second chance to refuse.
    Both, because they fail differently: the threshold catches "nothing
    relevant was retrieved", and NOT_COVERED catches "something relevant was
    retrieved but it does not answer this".
    """

    model = "gemini-flash"

    def __init__(self, api_key: str, client=None) -> None:
        self._api_key = api_key
        self._client = client

    async def answer(self, question: str, chunks: list[RetrievedChunk]) -> Answer:
        if should_refuse(chunks):
            return refusal(chunks, self.model)

        citations = select_citations(chunks)
        passages = "\n\n".join(
            f"[{index + 1}] {chunk.text_display.strip()}"
            for index, chunk in enumerate(citations)
        )

        text = await self._complete(PROMPT.format(question=question, passages=passages))

        if not text or "NOT_COVERED" in text:
            return refusal(chunks, self.model)

        return Answer(
            text=text.strip(),
            citations=citations,
            refused=False,
            top_score=max(chunk.similarity for chunk in chunks),
            model=self.model,
        )

    async def _complete(self, prompt: str) -> str:
        import httpx

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.0-flash:generateContent"
        )
        payload = {"contents": [{"parts": [{"text": prompt}]}]}

        client = self._client or httpx.AsyncClient(timeout=30)
        try:
            response = await client.post(
                url, json=payload, headers={"x-goog-api-key": self._api_key}
            )
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            # §11: on failure, return the refusal — never a guess. A model
            # outage must not become a confident answer from thin context.
            return ""
        finally:
            if self._client is None:
                await client.aclose()
