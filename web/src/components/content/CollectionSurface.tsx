import Link from "next/link";
import { VideoCard } from "./VideoCard";
import type { CollectionItem } from "@/lib/collections";
import { cn, formatTimecode } from "@/lib/utils";

/**
 * One surface, four routes — §6.2 on the web side.
 *
 * Subscriptions, History, Watch Later, and Liked all render through this. The
 * only thing that varies is the membership rule, and that lives in the API.
 * Building four page components would have produced four sets of empty states,
 * four grid definitions, and four slightly different ideas of what a signed-out
 * visitor should see.
 */

function SignedOut({ title }: { title: string }) {
  return (
    <div className="mx-auto max-w-[46ch] py-24 text-center">
      <h1 className="text-(length:--step-3)">{title}</h1>
      <p className="mt-3 text-pretty text-(length:--step--1) text-muted">
        This is yours, so it needs an account.
      </p>
      <Link
        href="/login"
        className={cn(
          "mt-6 inline-block rounded-(--radius-sm) bg-ink px-4 py-2",
          "text-(length:--step--1) font-medium text-canvas hover:opacity-90",
        )}
      >
        Sign in
      </Link>
    </div>
  );
}

/**
 * How far into a talk you got.
 *
 * A bar rather than a number: the useful question on a history page is "how
 * much is left", which a proportion answers at a glance and "742 seconds" does
 * not. The timecode is still there for anyone who wants it.
 */
function ResumeBar({ context, duration }: { context: CollectionItem["context"]; duration: number | null }) {
  if (!context?.position_sec || !duration) return null;

  const progress = Math.min(1, context.position_sec / duration);

  return (
    <div className="mt-2">
      <div className="h-[3px] w-full overflow-hidden rounded-(--radius-none) bg-rule">
        <div
          aria-hidden="true"
          className="h-full origin-left bg-ink"
          style={{ transform: `scaleX(${progress})` }}
        />
      </div>
      <p className="mt-1.5 font-mono text-(length:--step--2) text-muted">
        {context.completed
          ? "Finished"
          : `Stopped at ${formatTimecode(context.position_sec)}`}
      </p>
    </div>
  );
}

/**
 * The moment in a talk that answered the brief, on an AI-composed playlist.
 *
 * This is the whole argument for building playlists on the transcript layer
 * rather than on titles: the list can say *where* each talk addresses the
 * thing you asked about, and send you straight there.
 */
function MatchedMoment({ context, videoId }: { context: CollectionItem["context"]; videoId: string }) {
  if (context?.start_sec === undefined) return null;

  return (
    <div className="mt-2">
      <Link
        href={`/watch/${videoId}?t=${context.start_sec}`}
        className="font-mono text-(length:--step--2) text-brand hover:underline"
      >
        Starts at {formatTimecode(context.start_sec)}
      </Link>
      {context.note && (
        <p className="mt-1 text-pretty text-(length:--step--2) text-muted">
          &ldquo;{context.note}&rdquo;
        </p>
      )}
    </div>
  );
}

export function CollectionSurface({
  title,
  emptyTitle,
  emptyBody,
  items,
  isSignedIn,
  filters,
}: {
  title: string;
  emptyTitle: string;
  emptyBody: string;
  items: CollectionItem[];
  isSignedIn: boolean;
  /** Optional sub-navigation, e.g. Watch later / Liked. */
  filters?: React.ReactNode;
}) {
  if (!isSignedIn) return <SignedOut title={title} />;

  return (
    <div className="py-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-(length:--step-3)">{title}</h1>
        {filters}
      </div>

      {items.length === 0 ? (
        <div className="mx-auto max-w-[46ch] py-24 text-center">
          <p className="text-(length:--step-1)">{emptyTitle}</p>
          <p className="mt-2 text-pretty text-(length:--step--1) text-muted">
            {emptyBody}
          </p>
        </div>
      ) : (
        <div
          className="mt-8 grid gap-x-4 gap-y-8"
          style={{ gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))" }}
        >
          {items.map((item) => (
            <div key={item.id}>
              <VideoCard video={item} />
              <ResumeBar context={item.context} duration={item.duration_sec} />
              <MatchedMoment context={item.context} videoId={item.id} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
