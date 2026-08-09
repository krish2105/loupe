import { cn, hashString } from "@/lib/utils";

/**
 * Stand-in thumbnail: a projected slide.
 *
 * Real thumbnails arrive with the media provider. Until then the grid still has
 * to look deliberate — §7.2 says the thumbnail grid *is* the design, and 57
 * grey rectangles would read as broken rather than pending.
 *
 * So this draws what the catalogue actually is: a slide on a screen in a dark
 * room, which is the same referent the palette comes from. The composition is
 * derived from the video id, so a given talk always looks like itself and the
 * grid has rhythm without any two cards being identical.
 *
 * Pure CSS and SVG — no image requests, so a 60-card feed costs nothing.
 */
export function SlideThumb({
  seed,
  className,
}: {
  seed: string;
  className?: string;
}) {
  const hash = hashString(seed);

  // Three deterministic knobs: how many text lines, how wide they are, and
  // whether the slide carries a figure block.
  const lineCount = 3 + (hash % 3);
  const hasFigure = (hash >> 3) % 3 !== 0;
  const headingWidth = 42 + ((hash >> 5) % 30);

  const lines = Array.from({ length: lineCount }, (_, index) => {
    const local = hashString(`${seed}:${index}`);
    return 28 + (local % 46);
  });

  return (
    <div
      className={cn(
        "relative isolate overflow-hidden bg-hall",
        // A faint vignette: the room around the screen.
        "before:absolute before:inset-0 before:bg-[radial-gradient(120%_90%_at_50%_0%,transparent,rgb(0_0_0/0.35))]",
        className,
      )}
      aria-hidden="true"
    >
      <svg
        viewBox="0 0 320 180"
        preserveAspectRatio="none"
        className="size-full"
      >
        {/* The lit screen, built entirely from `screen` at varying alpha — the
            projection emits rather than merely being a lighter grey. Slightly
            off-centre so the grid does not read as a lattice.

            An earlier version drew this in `riser`, which measured 1.15:1
            against the canvas: the thumbnails were effectively invisible and
            the grid looked flat, which is fatal when the grid is the design. */}
        <rect
          x={26 + (hash % 10)}
          y={18}
          width={268}
          height={144}
          rx="2"
          className="fill-screen opacity-[0.11]"
        />

        <rect
          x={40 + (hash % 10)}
          y={38}
          width={(headingWidth / 100) * 240}
          height="9"
          rx="1.5"
          className="fill-screen opacity-[0.34]"
        />

        {lines.map((width, index) => (
          <rect
            key={index}
            x={40 + (hash % 10)}
            y={62 + index * 15}
            width={(width / 100) * 240}
            height="5"
            rx="1"
            className="fill-screen opacity-[0.19]"
          />
        ))}

        {hasFigure && (
          <rect
            x={196 + (hash % 10)}
            y={62}
            width="82"
            height="72"
            rx="2"
            className="fill-screen opacity-[0.07]"
          />
        )}
      </svg>
    </div>
  );
}
