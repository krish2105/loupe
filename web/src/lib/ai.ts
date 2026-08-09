export const AI_URL = process.env.NEXT_PUBLIC_AI_URL ?? "";

/**
 * The AI service (§5) — summarising, ask-video, semantic search.
 *
 * Separate from the core API client on purpose: this is a different service
 * with a different failure posture. When it is unreachable the video page must
 * still render completely, because everything except the panel works without
 * it.
 */

export type Citation = {
  chunk_id: string;
  start_sec: number;
  end_sec: number;
  text: string;
  score: number;
};

export type AskResponse = {
  session_id: string;
  answer: string;
  refused: boolean;
  citations: Citation[];
  top_score: number;
  model: string;
};

export type KeyPoint = { text: string; start_sec: number };

export type SummaryResponse =
  | { available: true; tldr: string; key_points: KeyPoint[]; model: string }
  | { available: false; reason: string };

export async function getSummary(videoId: string): Promise<SummaryResponse | null> {
  if (!AI_URL) return null;
  try {
    const response = await fetch(`${AI_URL}/v1/videos/${videoId}/summary`, {
      cache: "no-store",
    });
    if (!response.ok) return null;
    return (await response.json()) as SummaryResponse;
  } catch {
    return null;
  }
}

export async function ask(
  videoId: string,
  question: string,
  sessionId: string | null,
): Promise<AskResponse | null> {
  if (!AI_URL) return null;
  try {
    const response = await fetch(`${AI_URL}/v1/videos/${videoId}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, session_id: sessionId }),
    });
    if (!response.ok) return null;
    return (await response.json()) as AskResponse;
  } catch {
    return null;
  }
}
