import { cn } from "@/lib/utils";

/**
 * The wordmark.
 *
 * `glyph` is a lens — two concentric circles, the same optical object the Mark
 * comes from. `full` sets the name in the display face and leans on its width
 * axis: width is magnification, so the word widens slightly at large sizes
 * rather than merely scaling.
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
        <svg
          viewBox="0 0 24 24"
          aria-hidden="true"
          className="size-[22px] text-screen"
          fill="none"
          stroke="currentColor"
        >
          <circle cx="12" cy="12" r="8.5" strokeWidth="1.6" />
          <circle cx="12" cy="12" r="3.4" strokeWidth="1.2" />
        </svg>
        <span className="sr-only">Loupe</span>
      </span>
    );
  }

  return (
    <span
      className={cn(
        "font-display text-screen",
        "[font-variation-settings:'wdth'_92]",
        "text-(length:--step-2) font-semibold tracking-[0.02em]",
        className,
      )}
    >
      Loupe
    </span>
  );
}
