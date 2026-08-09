import { API_URL } from "./api";
import type { VideoSummary } from "./catalogue";

/**
 * The four list surfaces, from one client.
 *
 * §6.2: one abstraction, four surfaces. The API declares each collection —
 * title, empty copy, membership — so nothing here re-states them. If the empty
 * copy for Watch Later were written in the web app instead, it would be the
 * one place a fifth surface could be added inconsistently.
 */

export type CollectionKey =
  | "history"
  | "watch_later"
  | "liked"
  | "subscriptions";

/** Membership-specific extras. History carries a resume position. */
export type ItemContext = {
  position_sec?: number;
  watch_pct?: number;
  completed?: boolean;
};

export type CollectionItem = VideoSummary & { context?: ItemContext };

export type CollectionPayload = {
  key: string;
  title: string;
  empty_title: string;
  empty_body: string;
  items: CollectionItem[];
};

export type PlaylistSummary = {
  id: string;
  title: string;
  description: string | null;
  visibility: string;
  generated_by: "user" | "ai";
  rationale: string | null;
  item_count: number;
};

async function authed<T>(path: string, token: string | null): Promise<T | null> {
  if (!API_URL || !token) return null;

  try {
    const response = await fetch(`${API_URL}${path}`, {
      cache: "no-store",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export const getCollection = (key: CollectionKey, token: string | null) =>
  authed<CollectionPayload>(`/v1/me/collections/${key}`, token);

export type VideoState = {
  watch_later: boolean;
  liked: boolean;
  subscribed: boolean;
};

export const getVideoState = (videoId: string, token: string | null) =>
  authed<VideoState>(`/v1/me/state/${videoId}`, token);

export type SubscribedChannel = {
  id: string;
  handle: string;
  name: string;
  avatar_url: string | null;
};

export const getSubscribedChannels = (token: string | null) =>
  authed<{ items: SubscribedChannel[] }>("/v1/me/channels", token);

export const getPlaylists = (token: string | null) =>
  authed<{ items: PlaylistSummary[] }>("/v1/me/playlists", token);

export const getPlaylist = (id: string, token: string | null) =>
  authed<{
    id: string;
    title: string;
    description: string | null;
    generated_by: "user" | "ai";
    rationale: string | null;
    is_owner: boolean;
    items: CollectionItem[];
  }>(`/v1/me/playlists/${id}`, token);
