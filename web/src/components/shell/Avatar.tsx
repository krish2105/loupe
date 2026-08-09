import { cn, hashString } from "@/lib/utils";

/**
 * A channel or person avatar.
 *
 * An initial on a deterministic tint rather than a grey circle, so a sidebar of
 * eight channels reads as eight distinct things. The tint is derived from the
 * name, so it is stable across renders, deploys, and machines without storing
 * anything.
 *
 * Hue is constrained away from the brand red, so a generated avatar can never
 * be mistaken for a branded state.
 *
 * There is deliberately no image branch. No channel or user in the system has
 * an avatar_url yet, and an unreachable code path is worse than an absent one —
 * it looks tested and is not. Real images go in when there are real images.
 */
export function Avatar({
  name,
  size = 24,
  className,
}: {
  name: string;
  size?: number;
  className?: string;
}) {
  // 40°–330°, skipping the red wedge the brand occupies.
  const hue = 40 + (hashString(name) % 290);

  return (
    <span
      aria-hidden="true"
      style={{
        width: size,
        height: size,
        background: `oklch(0.62 0.13 ${hue})`,
        fontSize: Math.max(10, size * 0.42),
      }}
      className={cn(
        "grid shrink-0 place-items-center rounded-full font-medium text-white",
        className,
      )}
    >
      {name.slice(0, 1).toUpperCase()}
    </span>
  );
}
