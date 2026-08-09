"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Icon } from "@/components/shell/Icon";
import { API_URL } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import type { Episode } from "@/lib/audio";
import {
  DownloadFailed,
  downloadEpisode,
  isDownloaded,
  removeDownload,
  storageEstimate,
} from "./download";
import { cn } from "@/lib/utils";

/**
 * Download an episode for offline listening (ADR 0003).
 *
 * The button owns the transfer and the two rows either side of it: the API is
 * told when a download starts and again when it finishes with a size, because
 * "started and never finished" and "finished" are different states and only the
 * first one deserves a retry.
 *
 * The cache is the source of truth for whether something is playable offline.
 * The server row says what this person asked for on any device; the cache says
 * what this device actually holds. When they disagree, the cache wins, because
 * it is the one that decides whether pressing play works.
 */

type State =
  | { kind: "idle" }
  | { kind: "checking" }
  | { kind: "downloading"; percent: number | null }
  | { kind: "done" }
  | { kind: "error"; message: string };

export function DownloadButton({ episode }: { episode: Episode }) {
  const [state, setState] = useState<State>({ kind: "checking" });
  const abortRef = useRef<AbortController | null>(null);

  const downloadable =
    episode.source_class === "owned" && Boolean(episode.hls_url);

  useEffect(() => {
    if (!downloadable) return;

    let cancelled = false;
    void isDownloaded(episode.hls_url!).then((present) => {
      if (!cancelled) setState({ kind: present ? "done" : "idle" });
    });

    return () => {
      cancelled = true;
      abortRef.current?.abort();
    };
  }, [episode.hls_url, downloadable]);

  const record = useCallback(
    async (bytes: number | null, remove = false) => {
      if (!API_URL) return;

      const supabase = createClient();
      const token = supabase
        ? (await supabase.auth.getSession()).data.session?.access_token
        : null;
      // Signed-out listeners still get the download — the bytes are on their
      // device either way. They just get no row, and no second device knowing
      // about it.
      if (!token) return;

      await fetch(`${API_URL}/v1/me/downloads/${episode.id}`, {
        method: remove ? "DELETE" : "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: remove ? undefined : JSON.stringify({ bytes }),
      }).catch(() => {
        // The accounting row is not what makes offline work. Losing it is worth
        // no interruption.
      });
    },
    [episode.id],
  );

  async function start() {
    const controller = new AbortController();
    abortRef.current = controller;

    setState({ kind: "downloading", percent: null });
    void record(null);

    try {
      const room = await storageEstimate();
      if (room && room.quota - room.usage < 50_000_000) {
        throw new DownloadFailed("Not enough space left on this device.");
      }

      const bytes = await downloadEpisode(episode.hls_url!, {
        signal: controller.signal,
        onProgress: ({ receivedBytes, totalBytes }) =>
          setState({
            kind: "downloading",
            percent: totalBytes ? Math.round((receivedBytes / totalBytes) * 100) : null,
          }),
      });

      void record(bytes);
      setState({ kind: "done" });
    } catch (error) {
      if (controller.signal.aborted) {
        setState({ kind: "idle" });
        return;
      }

      void record(null, true);
      setState({
        kind: "error",
        message:
          error instanceof DownloadFailed
            ? error.message
            : "The download did not finish. Try again.",
      });
    }
  }

  async function remove() {
    setState({ kind: "checking" });
    await removeDownload(episode.hls_url!);
    void record(null, true);
    setState({ kind: "idle" });
  }

  if (!downloadable) return null;

  if (state.kind === "downloading") {
    return (
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => abortRef.current?.abort()}
          className={cn(
            "flex items-center gap-2 rounded-(--radius-pill) border border-rule",
            "px-3 py-1.5 text-(length:--step--2) text-muted hover:border-brand hover:text-brand",
          )}
        >
          {state.percent === null ? "Downloading…" : `${state.percent}%`}
          <span aria-hidden="true">×</span>
          <span className="sr-only">Cancel download</span>
        </button>
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={start}
          className={cn(
            "flex items-center gap-1.5 rounded-(--radius-pill) border border-rule",
            "px-3 py-1.5 text-(length:--step--2) text-danger",
          )}
        >
          <Icon name="download" className="size-4" />
          Retry
        </button>
        <span className="text-(length:--step--2) text-muted">{state.message}</span>
      </div>
    );
  }

  return (
    <button
      type="button"
      disabled={state.kind === "checking"}
      onClick={state.kind === "done" ? remove : start}
      title={state.kind === "done" ? "Remove download" : "Download to listen offline"}
      className={cn(
        "flex items-center gap-1.5 rounded-(--radius-pill) border px-3 py-1.5",
        "text-(length:--step--2) transition-colors disabled:opacity-40",
        state.kind === "done"
          ? "border-brand text-brand"
          : "border-rule text-muted hover:border-brand hover:text-brand",
      )}
    >
      <Icon name="download" className="size-4" />
      {state.kind === "done" ? "Downloaded" : "Download"}
    </button>
  );
}
