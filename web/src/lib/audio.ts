import { API_URL } from "./api";
import type { VideoSummary } from "./catalogue";

/**
 * Audio mode's reads (ADR 0003).
 *
 * There is no `AudioEpisode` type. An episode is a `VideoSummary` with
 * `content_kind: "audio"`, which is the whole argument of the data-model note:
 * the shape is the same and only the playback surface differs.
 */

export type Episode = VideoSummary & { hls_url: string | null };

/**
 * One readable line of transcript, built from word timings rather than from a
 * retrieval chunk. Chunks are sized for answering questions, not for reading
 * along: on a forty-minute episode one is three and a half minutes of text.
 */
export type Line = {
  index: number;
  start_sec: number;
  end_sec: number;
  speaker: string | null;
  text: string;
};

async function read<T>(path: string): Promise<T | null> {
  if (!API_URL) return null;

  try {
    const response = await fetch(`${API_URL}${path}`, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export const getEpisodes = (limit = 24) =>
  read<{ items: Episode[] }>(`/v1/listen?limit=${limit}`);

export const getTranscript = (videoId: string) =>
  read<{ available: boolean; lines: Line[] }>(`/v1/videos/${videoId}/transcript`);

export const getRadio = (videoId: string) =>
  read<{ source: "similarity" | "same_show"; items: Episode[] }>(
    `/v1/videos/${videoId}/radio`,
  );
