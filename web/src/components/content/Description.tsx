"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

/**
 * Description with expand.
 *
 * Collapsed height is fixed rather than animated: §7.7 forbids layout shift
 * from animation, and animating height:auto is the classic way to cause it.
 * The toggle is a real button, so it works from the keyboard without help.
 */
export function Description({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = text.length > 220;

  return (
    <div className="rounded-(--radius-md) bg-surface p-4">
      <p
        className={cn(
          "whitespace-pre-line text-pretty text-(length:--step--1)",
          !expanded && isLong && "line-clamp-3",
        )}
      >
        {text}
      </p>

      {isLong && (
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          className="mt-2 text-(length:--step--1) font-medium text-muted hover:text-ink"
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
}
