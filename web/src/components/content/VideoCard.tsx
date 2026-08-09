"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { Avatar } from "@/components/shell/Avatar";
import { MarkNode } from "@/components/mark/Mark";
import { Thumbnail } from "./Thumbnail";
import type { VideoSummary } from "@/lib/catalogue";
import { cn, formatAge, formatTimecode, formatViews } from "@/lib/utils";

/**
 * The video card, in three densities (§7.5).
 *
 *   grid     the home feed
 *   row      the related rail and search results
 *   compact  playlists and history
 *
 * Hand-built, never generated: §8.1 rule 2 keeps the video card in hand,
 * because it is the single most repeated object in the product.
 *
 * Capability-aware throughout. §4.2 rule 4 wants the unavailable states
 * designed rather than retrofitted, so the card reads its flags instead of
 * assuming every talk can do everything.
 */

type Density = "grid" | "row" | "compact";

/**
 * Says what the talk can do, only when it is worth saying.
 *
 * Nothing is shown for ordinary referenced content: forty-eight cards each
 * announcing an absence would make the common case look broken.
 */
function CapabilityBadge({ video }: { video: VideoSummary }) {
  if (video.capabilities.askable) {
    return (
      <span className="mt-1 inline-flex items-center gap-1.5 text-(length:--step--2) text-muted">
        <MarkNode />
        Searchable inside
      </span>
    );
  }

  if (video.capabilities.processing) {
    return (
      <span className="mt-1 block text-(length:--step--2) text-muted">
        Indexing — watchable now
      </span>
    );
  }

  return null;
}

export function VideoCard({
  video,
  density = "grid",
  priority = false,
}: {
  video: VideoSummary;
  density?: Density;
  /** Set on the first row so the largest visible image is not lazy-loaded. */
  priority?: boolean;
}) {
  const reduce = useReducedMotion();
  const href = `/watch/${video.id}`;
  const isRow = density !== "grid";

  return (
    <motion.article
      className={cn("group", isRow && "flex gap-2")}
      whileHover={reduce ? undefined : { y: -2 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
    >
      <Link
        href={href}
        className={cn(
          "relative block shrink-0 overflow-hidden rounded-(--radius-md)",
          density === "grid" && "aspect-video w-full",
          density === "row" && "aspect-video w-[168px]",
          density === "compact" && "aspect-video w-[120px]",
        )}
      >
        {/* Only transform and opacity animate (§7.3) — scaling the image inside
            a clipped box is the cheapest way to get the lift. */}
        <div
          className={cn(
            "size-full transition-transform duration-500",
            "[transition-timing-function:var(--ease-out-expo)]",
            !reduce && "group-hover:scale-[1.04]",
          )}
        >
          <Thumbnail
            seed={video.id}
            title={video.title}
            priority={priority}
            className="size-full"
            sizes={
              density === "grid"
                ? "(max-width: 640px) 100vw, (max-width: 1280px) 45vw, 24vw"
                : "180px"
            }
          />
        </div>

        {video.duration_sec ? (
          <span
            className={cn(
              "absolute bottom-1.5 right-1.5 rounded-(--radius-sm)",
              "bg-black/80 px-1.5 py-0.5",
              "font-mono text-(length:--step--2) text-white tabular-nums",
            )}
          >
            {formatTimecode(video.duration_sec)}
          </span>
        ) : null}
      </Link>

      <div className={cn("flex min-w-0 gap-3", density === "grid" && "mt-3")}>
        {density === "grid" && (
          <Link href={`/c/${video.channel.handle}`} className="mt-0.5 shrink-0">
            <Avatar name={video.channel.name} size={36} />
            <span className="sr-only">{video.channel.name}</span>
          </Link>
        )}

        <div className="min-w-0 flex-1">
          <h3
            className={cn(
              "font-sans font-medium leading-snug",
              density === "grid"
                ? "text-(length:--step-0)"
                : "text-(length:--step--1)",
            )}
          >
            <Link href={href} className="line-clamp-2">
              {video.title}
            </Link>
          </h3>

          <p className="mt-1 text-(length:--step--1) text-muted">
            <Link
              href={`/c/${video.channel.handle}`}
              className="transition-colors hover:text-ink"
            >
              {video.channel.name}
            </Link>
          </p>

          <p className="text-(length:--step--1) text-muted">
            {formatViews(video.view_count)} · {formatAge(video.published_at)}
          </p>

          <CapabilityBadge video={video} />
        </div>
      </div>
    </motion.article>
  );
}

/**
 * The loading shape.
 *
 * Matches the card's real geometry so nothing shifts when content arrives —
 * §7.7 forbids layout shift, and a skeleton of the wrong height causes it.
 */
export function VideoCardSkeleton({ density = "grid" }: { density?: Density }) {
  const isRow = density !== "grid";

  return (
    <div className={cn("animate-pulse", isRow && "flex gap-2")}>
      <div
        className={cn(
          "shrink-0 rounded-(--radius-md) bg-surface",
          density === "grid" && "aspect-video w-full",
          density === "row" && "aspect-video w-[168px]",
          density === "compact" && "aspect-video w-[120px]",
        )}
      />
      <div className={cn("flex min-w-0 flex-1 gap-3", density === "grid" && "mt-3")}>
        {density === "grid" && (
          <div className="size-9 shrink-0 rounded-full bg-surface" />
        )}
        <div className="min-w-0 flex-1">
          <div className="h-3.5 w-[92%] rounded-(--radius-sm) bg-surface" />
          <div className="mt-2 h-3.5 w-[64%] rounded-(--radius-sm) bg-surface" />
          <div className="mt-3 h-3 w-[44%] rounded-(--radius-sm) bg-surface" />
        </div>
      </div>
    </div>
  );
}
