"use client";

import { usePlayerControls } from "@/components/player/PlayerContext";
import { MarkNode } from "@/components/mark/Mark";
import type { KeyPoint } from "@/lib/ai";
import { cn, formatTimecode } from "@/lib/utils";

/**
 * The summary block — §11's summariser output.
 *
 * Every key point carries a start_sec and every key point is a button. That is
 * the whole reason the contract specifies timestamps on key points: a summary
 * you can read is ordinary, and a summary where each point is a place you can
 * jump to is the product.
 */
export function SummaryBlock({
  tldr,
  keyPoints,
}: {
  tldr: string;
  keyPoints: KeyPoint[];
}) {
  const { seek, play, setMarks } = usePlayerControls();

  return (
    <div>
      <p className="text-pretty text-(length:--step--1)">{tldr}</p>

      {keyPoints.length > 0 && (
        <ol className="mt-3 space-y-1">
          {keyPoints.map((point) => (
            <li key={point.start_sec}>
              <button
                type="button"
                onClick={() => {
                  seek(point.start_sec);
                  play();
                  // Show where every key point is, so the scrubber becomes a
                  // map of the summary.
                  setMarks(keyPoints.map((item) => item.start_sec));
                }}
                className={cn(
                  "flex w-full items-baseline gap-2 rounded-(--radius-sm) px-2 py-1.5 text-left",
                  "transition-colors hover:bg-surface",
                )}
              >
                <span className="shrink-0 font-mono text-(length:--step--2) text-brand">
                  {formatTimecode(point.start_sec)}
                </span>
                <span className="text-pretty text-(length:--step--2) text-muted">
                  {point.text}
                </span>
              </button>
            </li>
          ))}
        </ol>
      )}

      <p className="mt-3 flex items-center gap-1.5 text-(length:--step--2) text-muted">
        <MarkNode />
        Drawn from the transcript. Every point links to where it is said.
      </p>
    </div>
  );
}
