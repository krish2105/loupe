import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));

/**
 * Format seconds as a timecode.
 *
 * Citations, chapters, and the scrubber all render timestamps, and they must
 * agree exactly — §11.1 makes the whole intelligence layer depend on a
 * timestamp landing on the right moment, so there is one formatter, not three.
 * Hours are shown only when the talk is long enough to have them.
 */
export function formatTimecode(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const seconds = safe % 60;
  const pad = (n: number) => n.toString().padStart(2, "0");

  return hours > 0
    ? `${hours}:${pad(minutes)}:${pad(seconds)}`
    : `${minutes}:${pad(seconds)}`;
}

/** "12K views", not "12,431 views" — the exact number is never the point. */
export function formatViews(count: number): string {
  if (count < 1000) return `${count} view${count === 1 ? "" : "s"}`;
  if (count < 1_000_000) return `${Math.round(count / 100) / 10}K views`;
  return `${Math.round(count / 100_000) / 10}M views`;
}

/**
 * Age as a person would say it.
 *
 * Deterministic given a reference time, which the caller passes so a server
 * render and a client render cannot disagree and cause hydration noise.
 */
export function formatAge(iso: string | null, now: number = Date.now()): string {
  if (!iso) return "";

  const seconds = Math.max(0, (now - new Date(iso).getTime()) / 1000);
  const units: [number, string][] = [
    [31_536_000, "year"],
    [2_592_000, "month"],
    [604_800, "week"],
    [86_400, "day"],
    [3_600, "hour"],
    [60, "minute"],
  ];

  for (const [size, name] of units) {
    const value = Math.floor(seconds / size);
    if (value >= 1) return `${value} ${name}${value === 1 ? "" : "s"} ago`;
  }
  return "just now";
}

/** Small stable hash, for deriving deterministic visuals from an id. */
export function hashString(input: string): number {
  let hash = 2166136261;
  for (let i = 0; i < input.length; i++) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return Math.abs(hash);
}
