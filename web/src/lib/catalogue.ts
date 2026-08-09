import { API_URL } from "./api";

/**
 * Typed reads from the core API.
 *
 * §5 keeps the web app off the database: the core API owns CRUD and feed
 * assembly. That boundary is what lets the feed change shape in Phase 9
 * without the UI knowing.
 */

export type Capabilities = {
  playable: boolean;
  searchable_inside: boolean;
  askable: boolean;
  has_chapters: boolean;
  processing: boolean;
};

export type ChannelRef = {
  id: string;
  handle: string;
  name: string;
  avatar_url: string | null;
};

export type VideoSummary = {
  id: string;
  title: string;
  description: string | null;
  duration_sec: number | null;
  published_at: string | null;
  source_class: "owned" | "referenced";
  processing_status: string;
  channel: ChannelRef;
  view_count: number;
  comment_count: number;
  capabilities: Capabilities;
};

export type VideoDetail = VideoSummary & { hls_url: string | null };

export type CommentAuthor = {
  id: string;
  handle: string;
  display_name: string;
  avatar_url: string | null;
};

export type Comment = {
  id: string;
  body: string;
  created_at: string;
  edited_at: string | null;
  author: CommentAuthor;
  replies: Comment[];
};

/**
 * One place that knows the API might be absent.
 *
 * The API is not deployed yet, so every page has to render something sensible
 * without it. Returning null rather than throwing keeps that decision with the
 * page, which is the only place that knows what an empty version of itself
 * should say.
 */
async function get<T>(path: string): Promise<T | null> {
  if (!API_URL) return null;

  try {
    const response = await fetch(`${API_URL}${path}`, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export const getFeed = (
  limit = 24,
  options: { cursor?: string; only?: "searchable" } = {},
) => {
  const params = new URLSearchParams({ limit: String(limit) });
  if (options.cursor) params.set("cursor", options.cursor);
  if (options.only) params.set("only", options.only);

  return get<{ items: VideoSummary[]; next_cursor: string | null }>(
    `/v1/feed?${params}`,
  );
};

export const getVideo = (id: string) => get<VideoDetail>(`/v1/videos/${id}`);

export const getRelated = (id: string, limit = 8) =>
  get<{ items: VideoSummary[] }>(`/v1/videos/${id}/related?limit=${limit}`);

export const getChannel = (handle: string) =>
  get<{ channel: ChannelRef & { description: string | null; source_class: string }; videos: VideoSummary[] }>(
    `/v1/channels/${encodeURIComponent(handle)}`,
  );

export const getComments = (videoId: string) =>
  get<{ items: Comment[] }>(`/v1/videos/${videoId}/comments`);
