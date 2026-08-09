"use client";

import { Icon } from "@/components/shell/Icon";
import { useQueueControls, useQueueState } from "./QueueContext";
import { cn, formatTimecode } from "@/lib/utils";

/**
 * What is playing and what is next.
 *
 * Reordering is buttons rather than drag-and-drop, and that is a decision. Drag
 * on a list like this needs pointer events, a keyboard equivalent, an
 * announcement for screen readers, and touch handling that does not fight the
 * page scroll. Up and down buttons are all four of those for free, work on a
 * phone, and are what someone using a keyboard gets anyway.
 */
export function QueuePanel({ onClose }: { onClose: () => void }) {
  const { state, current, upcoming } = useQueueState();
  const { jumpTo, remove, move, clear } = useQueueControls();

  const startOfUpcoming = state.cursor + 1;

  return (
    <aside
      aria-label="Queue"
      className={cn(
        "fixed bottom-[calc(var(--miniplayer-height)+env(safe-area-inset-bottom))]",
        "right-0 z-40 flex max-h-[60dvh] w-full flex-col border border-rule",
        "bg-canvas shadow-lg sm:right-4 sm:w-[380px] sm:rounded-(--radius-md)",
      )}
    >
      <header className="flex items-center justify-between border-b border-rule px-4 py-3">
        <h2 className="text-(length:--step--1) font-medium">Queue</h2>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={clear}
            className="rounded-(--radius-sm) px-2 py-1 text-(length:--step--2) text-muted hover:text-ink"
          >
            Clear
          </button>
          <button
            type="button"
            onClick={onClose}
            title="Close queue"
            className="grid size-8 place-items-center rounded-full text-muted hover:bg-surface"
          >
            <Icon name="create" className="size-4 rotate-45" />
            <span className="sr-only">Close queue</span>
          </button>
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {current && (
          <div className="border-b border-rule px-4 py-3">
            <p className="text-(length:--step--2) text-muted">Playing</p>
            <p className="mt-1 truncate text-(length:--step--1) font-medium">
              {current.title}
            </p>
            <p className="truncate text-(length:--step--2) text-muted">
              {current.channelName}
            </p>
          </div>
        )}

        {upcoming.length === 0 ? (
          <p className="px-4 py-8 text-center text-(length:--step--2) text-muted">
            Nothing queued after this one.
          </p>
        ) : (
          <ol className="divide-y divide-rule">
            {upcoming.map((track, index) => {
              const position = startOfUpcoming + index;

              return (
                <li key={`${track.id}-${position}`} className="flex items-center gap-2 px-3 py-2">
                  <button
                    type="button"
                    onClick={() => jumpTo(position)}
                    className="min-w-0 flex-1 text-left"
                  >
                    <span className="block truncate text-(length:--step--1)">
                      {track.title}
                    </span>
                    <span className="block truncate text-(length:--step--2) text-muted">
                      {track.channelName}
                      {track.durationSec
                        ? ` · ${formatTimecode(track.durationSec)}`
                        : ""}
                    </span>
                  </button>

                  <QueueButton
                    label={`Move ${track.title} up`}
                    disabled={index === 0}
                    onClick={() => move(position, position - 1)}
                  >
                    ↑
                  </QueueButton>
                  <QueueButton
                    label={`Move ${track.title} down`}
                    disabled={index === upcoming.length - 1}
                    onClick={() => move(position, position + 1)}
                  >
                    ↓
                  </QueueButton>
                  <QueueButton
                    label={`Remove ${track.title} from the queue`}
                    onClick={() => remove(position)}
                  >
                    ×
                  </QueueButton>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </aside>
  );
}

function QueueButton({
  label,
  onClick,
  disabled = false,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={label}
      className={cn(
        "grid size-7 shrink-0 place-items-center rounded-(--radius-sm)",
        "font-mono text-(length:--step--2) text-muted transition-colors",
        "hover:bg-surface hover:text-ink disabled:opacity-30 disabled:hover:bg-transparent",
      )}
    >
      {children}
      <span className="sr-only">{label}</span>
    </button>
  );
}
