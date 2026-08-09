import Image from "next/image";
import { cn, hashString } from "@/lib/utils";

/**
 * A talk's thumbnail.
 *
 * Real photography rather than the generated slide placeholder, because a grid
 * of wireframes reads as unfinished no matter how well it is drawn.
 *
 * These are stock images keyed to the talk id — the same talk always gets the
 * same picture — not frames from the video. Actual frames arrive when the media
 * provider generates sprite sheets. This is recorded in the README rather than
 * left for someone to discover.
 */
export function Thumbnail({
  seed,
  title,
  className,
  priority = false,
  sizes = "(max-width: 640px) 100vw, (max-width: 1280px) 50vw, 25vw",
}: {
  seed: string;
  title: string;
  className?: string;
  /** Set on the first row so the largest visible image is not lazy-loaded. */
  priority?: boolean;
  sizes?: string;
}) {
  // A stable integer keeps the same talk on the same image across renders,
  // deploys, and machines.
  const imageId = hashString(seed) % 1000;

  return (
    <div className={cn("relative overflow-hidden bg-surface", className)}>
      <Image
        src={`https://picsum.photos/seed/loupe-${imageId}/640/360`}
        alt=""
        fill
        sizes={sizes}
        priority={priority}
        className="object-cover"
      />
      {/* Decorative: the title is already the card's heading, so announcing the
          image again would just make a screen reader read everything twice. */}
      <span className="sr-only">{title}</span>
    </div>
  );
}
