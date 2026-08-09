import Link from "next/link";
import { MarkNode } from "@/components/mark/Mark";
import { SlideThumb } from "./SlideThumb";
import type { VideoSummary } from "@/lib/catalogue";
import { cn, formatAge, formatTimecode, formatViews } from "@/lib/utils";

/**
 * The video card, in three densities (§7.5).
 *
 *   grid     the home feed
 *   row      the related rail and search results
 *   compact  playlists and history
 *
 * Hand-built, never generated: §8.1 rule 2 reserves the MCP for primitives and
 * keeps the video card in hand, because it is the single most repeated object
 * in the product and a generated one arrives with its own opinions.
 *
 * Capability-aware throughout. §4.2 rule 4 wants the unavailable states
 * designed early rather than retrofitted, so the card reads its flags rather
 * than assuming every talk can do everything.
 */

type Density = "grid" | "row" | "compact";

function Meta({ video }: { video: VideoSummary }) {
  return (
    <p className="mt-1 text-(length:--step--1) text-dust">
      {formatViews(video.view_count)} · {formatAge(video.published_at)}
    </p>
  );
}

/**
 * Says what the talk can do, only when it is worth saying.
 *
 * Nothing is shown for ordinary referenced content: 48 cards each announcing
 * an absence would make the common case look broken. The Mark appears only
 * where a capability exists.
 */
function CapabilityBadge({ video }: { video: VideoSummary }) {
  if (video.capabilities.askable) {
    return (
      <span className="inline-flex items-center gap-1.5 text-(length:--step--2) text-dust">
        <MarkNode />
        Searchable
      </span>
    );
  }

  if (video.capabilities.processing) {
    return (
      <span className="text-(length:--step--2) text-dust">
        Indexing — watchable now
      </span>
    );
  }

  return null;
}

export function VideoCard({
  video,
  density = "grid",
}: {
  video: VideoSummary;
  density?: Density;
}) {
  const href = `/watch/${video.id}`;
  const isRow = density === "row" || density === "compact";

  const thumbnail = (
    <div
      className={cn(
        "relative shrink-0 overflow-hidden rounded-(--radius-md)",
        density === "grid" && "aspect-video w-full",
        density === "row" && "aspect-video w-[168px]",
        density === "compact" && "aspect-video w-[120px]",
      )}
    >
      <SlideThumb seed={video.id} className="size-full" />

      {video.duration_sec ? (
        <span
          className={cn(
            "absolute bottom-1.5 right-1.5 rounded-(--radius-sm)",
            "bg-black/75 px-1.5 py-0.5",
            "font-mono text-(length:--step--2) text-white tabular-nums",
          )}
        >
          {formatTimecode(video.duration_sec)}
        </span>
      ) : null}
    </div>
  );

  return (
    <article className={cn("group", isRow && "flex gap-3")}>
      <Link href={href} className="block shrink-0 rounded-(--radius-md)">
        {thumbnail}
      </Link>

      <div className={cn("min-w-0", density === "grid" && "mt-3")}>
        <h3
          className={cn(
            // Titles are body face, not display: at this density the display
            // face would fight the grid rather than lead it.
            "font-sans font-medium leading-snug",
            density === "grid"
              ? "text-(length:--step-0)"
              : "text-(length:--step--1)",
          )}
        >
          <Link
            href={href}
            className="line-clamp-2 transition-colors hover:text-dust"
          >
            {video.title}
          </Link>
        </h3>

        <p className="mt-1.5 text-(length:--step--1) text-dust">
          <Link
            href={`/c/${video.channel.handle}`}
            className="transition-colors hover:text-screen"
          >
            {video.channel.name}
          </Link>
        </p>

        <Meta video={video} />

        <div className="mt-1.5">
          <CapabilityBadge video={video} />
        </div>
      </div>
    </article>
  );
}

/**
 * The loading shape.
 *
 * Matches the card's real geometry so nothing shifts when content arrives —
 * §7.7 forbids layout shift, and a skeleton of the wrong height is the most
 * common cause of it.
 */
export function VideoCardSkeleton({ density = "grid" }: { density?: Density }) {
  const isRow = density !== "grid";

  return (
    <div className={cn("animate-pulse", isRow && "flex gap-3")}>
      <div
        className={cn(
          "shrink-0 rounded-(--radius-md) bg-riser",
          density === "grid" && "aspect-video w-full",
          density === "row" && "aspect-video w-[168px]",
          density === "compact" && "aspect-video w-[120px]",
        )}
      />
      <div className={cn("min-w-0 flex-1", density === "grid" && "mt-3")}>
        <div className="h-3.5 w-[92%] rounded-(--radius-sm) bg-riser" />
        <div className="mt-2 h-3.5 w-[64%] rounded-(--radius-sm) bg-riser" />
        <div className="mt-3 h-3 w-[44%] rounded-(--radius-sm) bg-riser" />
      </div>
    </div>
  );
}
