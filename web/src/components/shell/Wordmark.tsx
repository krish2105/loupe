import { cn } from "@/lib/utils";

/**
 * The wordmark.
 *
 * A lens — two concentric circles with a play triangle at the centre, in the
 * brand red. Loupe's own mark, not a borrowed one: ADR 0002 permits the red
 * identity but keeps trademark firmly out of it.
 */
export function Wordmark({
  variant = "full",
  className,
}: {
  variant?: "glyph" | "full";
  className?: string;
}) {
  if (variant === "glyph") {
    return (
      <span className={cn("grid place-items-center", className)}>
        <svg viewBox="0 0 28 28" aria-hidden="true" className="size-7">
          <circle cx="14" cy="14" r="12" className="fill-brand" />
          <circle
            cx="14"
            cy="14"
            r="7.5"
            fill="none"
            stroke="white"
            strokeWidth="1.4"
            opacity="0.55"
          />
          <path d="M11.8 10.3 18 14l-6.2 3.7z" fill="white" />
        </svg>
        <span className="sr-only">Loupe</span>
      </span>
    );
  }

  return (
    <span
      className={cn(
        "font-display text-ink",
        "[font-variation-settings:'wdth'_92]",
        "text-(length:--step-2) font-semibold tracking-[-0.01em]",
        className,
      )}
    >
      Loupe
    </span>
  );
}
