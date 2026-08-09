/**
 * The Mark — Loupe's signature element.
 *
 * One graphic primitive meaning "this exact moment", rendered at several scales
 * but always the same object:
 *
 *   MarkNode       a node alone           → "AI ready" on a video card
 *   MarkUnderline  a stroke under text    → the matched span, the citation
 *   (MarkTick)     a tick on the scrubber → arrives with the player in Phase 1
 *
 * It is the only chromatic object in the product. In dark it is a stroke on
 * near-black; in light it becomes a highlighter ground behind near-black text.
 * Same gesture, different physics — which is why the two themes read as
 * designed rather than inverted.
 *
 * Hand-built, never generated: §8.1 rule 2 reserves the MCP for primitives and
 * keeps the signature moments in hand.
 */

import { cn } from "@/lib/utils";

export function MarkNode({
  className,
  label,
}: {
  className?: string;
  /** Give it a label when it stands alone; omit inside an already-labelled control. */
  label?: string;
}) {
  return (
    <span
      className={cn("inline-grid place-items-center align-middle", className)}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <span className="block size-[5px] rounded-full bg-brand" />
    </span>
  );
}

/**
 * Marks a span of text as found.
 *
 * Uses a real underline drawn with a background gradient rather than
 * `text-decoration`, so the stroke sits at a controlled distance from the
 * baseline and survives line wrapping — a matched phrase in a transcript
 * wraps constantly.
 */
export function MarkUnderline({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <mark
      className={cn(
        // `mark` carries its own browser styling; reset it and rebuild.
        "bg-transparent text-inherit",
        // Dark: a 2px stroke under the phrase.
        "[background-image:linear-gradient(var(--brand),var(--brand))]",
        "[background-size:100%_2px] [background-repeat:no-repeat]",
        "[background-position:0_calc(100%-1px)]",
        // Light: the stroke fills into a ground behind the text.
        "dark:[background-size:100%_2px]",
        "[&:where([data-theme=light]_*)]:bg-brand-ground",
        "[&:where([data-theme=light]_*)]:[background-image:none]",
        "[&:where([data-theme=light]_*)]:rounded-[2px]",
        "[&:where([data-theme=light]_*)]:box-decoration-clone",
        "[&:where([data-theme=light]_*)]:px-[0.15em]",
        className,
      )}
    >
      {children}
    </mark>
  );
}
