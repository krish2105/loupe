"use client";

import { useState } from "react";
import { MarkNode, MarkUnderline } from "@/components/mark/Mark";
import { usePlayerControls } from "@/components/player/PlayerContext";
import { ask, type AskResponse, type Citation } from "@/lib/ai";
import { cn, formatTimecode } from "@/lib/utils";

/**
 * Ask this talk — §11's ask-video, and §7.4's defining interaction.
 *
 *     "The citation seek. An answer timestamp is clicked; the player seeks and
 *      a marker pulses on the scrubber. This is the product's defining
 *      interaction."
 *
 * Clicking a citation does two things that are the same thing: it moves the
 * playhead, and the tick already on the scrubber is the mark in the sentence.
 * That is why marks live in the player store rather than here — one object,
 * two places.
 */

type Turn = { question: string; response: AskResponse | null };

function CitationChip({ citation }: { citation: Citation }) {
  const { seek, play } = usePlayerControls();

  return (
    <button
      type="button"
      onClick={() => {
        seek(citation.start_sec);
        play();
      }}
      title={citation.text}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-(--radius-sm)",
        "border border-rule bg-canvas px-2 py-1",
        "font-mono text-(length:--step--2) text-ink",
        "transition-colors hover:border-brand hover:text-brand",
      )}
    >
      <MarkNode />
      {formatTimecode(citation.start_sec)}
    </button>
  );
}

function Answer({ response }: { response: AskResponse }) {
  if (response.refused) {
    return (
      <div className="rounded-(--radius-md) border border-rule bg-canvas p-3">
        <p className="text-(length:--step--1) text-muted">{response.answer}</p>
        {/* §11.1 tracks refusal rate as a headline metric — a feature, not a
            defect — so the score that caused it is shown rather than hidden. */}
        <p className="mt-2 font-mono text-(length:--step--2) text-muted">
          best match {response.top_score.toFixed(2)} — below the threshold to
          answer from
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-(--radius-md) border border-rule bg-canvas p-3">
      <p className="whitespace-pre-line text-pretty text-(length:--step--1)">
        {response.answer}
      </p>

      {response.citations.length > 0 && (
        <div className="mt-3">
          <p className="text-(length:--step--2) text-muted">
            Jump to where this is said
          </p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {response.citations.map((citation) => (
              <CitationChip key={citation.chunk_id} citation={citation} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function AskThread({ videoId }: { videoId: string }) {
  const { setMarks } = usePlayerControls();
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const asked = question.trim();
    if (!asked || pending) return;

    setQuestion("");
    setPending(true);
    setTurns((current) => [...current, { question: asked, response: null }]);

    const response = await ask(videoId, asked, sessionId);

    setPending(false);
    setTurns((current) =>
      current.map((turn, index) =>
        index === current.length - 1 ? { ...turn, response } : turn,
      ),
    );

    if (response) {
      setSessionId(response.session_id);
      // The scrubber and the answer read the same marks.
      setMarks(response.citations.map((citation) => citation.start_sec));
    }
  }

  return (
    <div>
      <form onSubmit={submit}>
        <label htmlFor="ask" className="sr-only">
          Ask this talk a question
        </label>
        <div className="flex gap-2">
          <input
            id="ask"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask this talk a question"
            className={cn(
              "min-w-0 flex-1 rounded-(--radius-pill) border border-rule",
              "bg-canvas px-3.5 py-2 text-(length:--step--1)",
              "outline-none transition-colors placeholder:text-muted focus:border-brand",
            )}
          />
          <button
            type="submit"
            disabled={pending || !question.trim()}
            className={cn(
              "shrink-0 rounded-(--radius-pill) bg-brand px-4 py-2",
              "text-(length:--step--1) font-medium text-white",
              "transition-opacity hover:opacity-90 disabled:opacity-40",
            )}
          >
            {pending ? "Asking…" : "Ask"}
          </button>
        </div>
      </form>

      {turns.length === 0 ? (
        <p className="mt-3 text-pretty text-(length:--step--2) text-muted">
          Answers quote the talk and link to the moment. If the speaker does not
          cover it, Loupe says so rather than guessing.
        </p>
      ) : (
        <ol className="mt-4 space-y-4">
          {turns.map((turn, index) => (
            <li key={index}>
              <p className="text-(length:--step--1) font-medium">
                <MarkUnderline>{turn.question}</MarkUnderline>
              </p>
              <div className="mt-2">
                {turn.response === null ? (
                  pending && index === turns.length - 1 ? (
                    <p className="text-(length:--step--2) text-muted">
                      Searching the transcript…
                    </p>
                  ) : (
                    <p className="text-(length:--step--2) text-danger">
                      The answer did not come back. Try again.
                    </p>
                  )
                ) : (
                  <Answer response={turn.response} />
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
