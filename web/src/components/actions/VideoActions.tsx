"use client";

import { useState } from "react";
import { API_URL } from "@/lib/api";
import type { VideoState } from "@/lib/collections";
import { createClient } from "@/lib/supabase/client";
import { cn } from "@/lib/utils";

/**
 * The action bar: like, save, subscribe.
 *
 * Optimistic, and reverted on failure. These are two-state toggles where the
 * server almost always agrees, so waiting for a round-trip before showing the
 * change makes the product feel slower than it is — but silently keeping a
 * wrong state would be worse than the delay, so a failure puts it back and
 * says so.
 */

type Action =
  | { kind: "saved"; list: "watch_later" | "liked" }
  | { kind: "subscription"; channelId: string };

function pathFor(action: Action, videoId: string) {
  return action.kind === "saved"
    ? `/v1/me/saved/${action.list}/${videoId}`
    : `/v1/me/subscriptions/${action.channelId}`;
}

function ToggleButton({
  active,
  label,
  activeLabel,
  onToggle,
  icon,
}: {
  active: boolean;
  label: string;
  activeLabel: string;
  onToggle: () => void;
  icon: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={active}
      className={cn(
        "inline-flex items-center gap-2 rounded-(--radius-pill) border px-3.5 py-1.5",
        "text-(length:--step--1) transition-colors",
        active
          ? "border-ink bg-ink text-canvas"
          : "border-rule bg-surface text-muted hover:text-ink",
      )}
    >
      {icon}
      {/* The label states what is true now, and the pressed state carries the
          rest — a button whose text flips between "Save" and "Saved" makes
          people read it twice to work out which. */}
      {active ? activeLabel : label}
    </button>
  );
}

export function VideoActions({
  videoId,
  channelId,
  initialState,
  isSignedIn,
}: {
  videoId: string;
  channelId: string;
  initialState: VideoState | null;
  isSignedIn: boolean;
}) {
  const [state, setState] = useState<VideoState>(
    initialState ?? { watch_later: false, liked: false, subscribed: false },
  );
  const [error, setError] = useState<string | null>(null);

  async function toggle(action: Action, key: keyof VideoState) {
    if (!isSignedIn) {
      setError("Sign in to keep talks.");
      return;
    }

    const supabase = createClient();
    const token = supabase
      ? (await supabase.auth.getSession()).data.session?.access_token
      : null;

    if (!token || !API_URL) {
      setError("This is not connected in this environment yet.");
      return;
    }

    const next = !state[key];
    setState((current) => ({ ...current, [key]: next }));
    setError(null);

    const response = await fetch(`${API_URL}${pathFor(action, videoId)}`, {
      method: next ? "PUT" : "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    }).catch(() => null);

    if (!response || !response.ok) {
      setState((current) => ({ ...current, [key]: !next }));
      setError("That did not save. Try again.");
    }
  }

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        <ToggleButton
          active={state.liked}
          label="Like"
          activeLabel="Liked"
          onToggle={() => toggle({ kind: "saved", list: "liked" }, "liked")}
          icon={
            <svg viewBox="0 0 20 20" aria-hidden="true" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.6">
              <path d="M10 16.5S3.5 12.6 3.5 8.2A3.2 3.2 0 0 1 10 6.6a3.2 3.2 0 0 1 6.5 1.6c0 4.4-6.5 8.3-6.5 8.3z" />
            </svg>
          }
        />

        <ToggleButton
          active={state.watch_later}
          label="Save"
          activeLabel="Saved"
          onToggle={() => toggle({ kind: "saved", list: "watch_later" }, "watch_later")}
          icon={
            <svg viewBox="0 0 20 20" aria-hidden="true" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.6">
              <path d="M5.5 3h9v14l-4.5-3.4L5.5 17z" />
            </svg>
          }
        />

        <ToggleButton
          active={state.subscribed}
          label="Subscribe"
          activeLabel="Subscribed"
          onToggle={() => toggle({ kind: "subscription", channelId }, "subscribed")}
          icon={
            <svg viewBox="0 0 20 20" aria-hidden="true" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
              <path d="M4 6.5h12M2.5 10h15M4 13.5h12" />
            </svg>
          }
        />
      </div>

      {error && (
        <p role="alert" className="mt-2 text-(length:--step--2) text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
