"use client";

import {
  buildOfflineMaster,
  findAudioRendition,
  findMediaFile,
} from "./hls-manifest";

/**
 * Downloading an episode for offline playback (ADR 0003).
 *
 * Runs in the page, not in the service worker. Cache Storage is available in
 * both, and doing it here means progress is a callback rather than a message
 * channel, a cancel is an AbortController rather than a protocol, and a failure
 * surfaces as a rejected promise on the button that started it. The service
 * worker's only job is serving what this put there.
 *
 * What gets stored, for one episode:
 *
 *   - a rewritten master playlist, offering only the audio rendition
 *   - the audio rendition's media playlist, unchanged
 *   - the audio file the playlist's byte ranges are cut from
 *
 * Three entries. The byte ranges are not stored separately: the service worker
 * slices them out of the one file on request, which trades a read per segment
 * for not holding a hundred near-duplicate cache entries.
 */

export const MEDIA_CACHE = "loupe-media-v1";

export type DownloadProgress = {
  receivedBytes: number;
  totalBytes: number | null;
};

export class DownloadFailed extends Error {}

/**
 * @param hlsUrl the episode's master playlist
 * @returns bytes stored, for the accounting row
 */
export async function downloadEpisode(
  hlsUrl: string,
  {
    signal,
    onProgress,
  }: { signal?: AbortSignal; onProgress?: (progress: DownloadProgress) => void } = {},
): Promise<number> {
  if (typeof caches === "undefined") {
    throw new DownloadFailed("This browser cannot store downloads.");
  }

  const cache = await caches.open(MEDIA_CACHE);

  const masterResponse = await fetch(hlsUrl, { signal });
  if (!masterResponse.ok) throw new DownloadFailed("Could not read the stream.");
  const masterText = await masterResponse.text();

  const rendition = findAudioRendition(masterText, hlsUrl);
  if (!rendition) {
    // Muxed streams cannot be stored as audio alone. Said plainly rather than
    // downloading video for a podcast.
    throw new DownloadFailed("This talk has no separate audio track to download.");
  }

  const playlistResponse = await fetch(rendition.url, { signal });
  if (!playlistResponse.ok) throw new DownloadFailed("Could not read the audio track.");
  const playlistText = await playlistResponse.text();

  const media = findMediaFile(playlistText, rendition.url);
  if (!media) throw new DownloadFailed("This talk's audio is in a format Loupe cannot store.");

  const bytes = await fetchWithProgress(media.url, media.lastByte, signal, onProgress);

  // Written last, and in this order. The master is what the player looks for
  // first, so storing it before its contents would leave a window where an
  // episode claims to be downloaded and then fails to play.
  await cache.put(media.url, mediaResponse(bytes));
  await cache.put(rendition.url, textResponse(playlistText, "application/x-mpegURL"));
  await cache.put(
    hlsUrl,
    textResponse(
      buildOfflineMaster(rendition, rendition.url),
      "application/x-mpegURL",
    ),
  );

  return bytes.byteLength;
}

export async function removeDownload(hlsUrl: string): Promise<void> {
  if (typeof caches === "undefined") return;

  const cache = await caches.open(MEDIA_CACHE);

  // The master is deleted first: while it is present the episode is playable,
  // and while it is absent nothing else in the cache can be reached. Deleting
  // it last would leave a window where playback starts and then stalls.
  await cache.delete(hlsUrl);

  for (const request of await cache.keys()) {
    if (request.url.startsWith(directoryOf(hlsUrl))) {
      await cache.delete(request);
    }
  }
}

export async function isDownloaded(hlsUrl: string): Promise<boolean> {
  if (typeof caches === "undefined") return false;
  const cache = await caches.open(MEDIA_CACHE);
  return (await cache.match(hlsUrl)) !== undefined;
}

/** What the device has left, for the warning before a large download. */
export async function storageEstimate(): Promise<{ usage: number; quota: number } | null> {
  if (typeof navigator === "undefined" || !navigator.storage?.estimate) return null;

  const { usage, quota } = await navigator.storage.estimate();
  if (usage === undefined || quota === undefined) return null;
  return { usage, quota };
}

/**
 * Read a response body, reporting progress.
 *
 * Streamed rather than awaited as a blob, because the whole point of a download
 * UI is that a twelve-megabyte transfer on a slow connection shows something
 * moving. `content-length` is a hint: it is absent on chunked responses, which
 * is why the playlist's own highest byte is the fallback total.
 */
async function fetchWithProgress(
  url: string,
  expectedBytes: number,
  signal: AbortSignal | undefined,
  onProgress?: (progress: DownloadProgress) => void,
): Promise<ArrayBuffer> {
  const response = await fetch(url, { signal });
  if (!response.ok || !response.body) {
    throw new DownloadFailed("Could not read the audio.");
  }

  const declared = Number(response.headers.get("content-length"));
  const total = Number.isFinite(declared) && declared > 0 ? declared : expectedBytes || null;

  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let received = 0;

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    if (value) {
      chunks.push(value);
      received += value.byteLength;
      onProgress?.({ receivedBytes: received, totalBytes: total });
    }
  }

  const merged = new Uint8Array(received);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.byteLength;
  }

  return merged.buffer;
}

function mediaResponse(bytes: ArrayBuffer): Response {
  return new Response(bytes, {
    status: 200,
    headers: {
      "Content-Type": "video/mp4",
      "Content-Length": String(bytes.byteLength),
      // Advertised so the service worker's slicing looks like what the network
      // would have done, rather than like a special case.
      "Accept-Ranges": "bytes",
    },
  });
}

function textResponse(body: string, contentType: string): Response {
  return new Response(body, {
    status: 200,
    headers: { "Content-Type": contentType },
  });
}

function directoryOf(url: string): string {
  return url.slice(0, url.lastIndexOf("/") + 1);
}
