/**
 * Just enough HLS manifest parsing to download an episode (ADR 0003).
 *
 * Not a general parser, and not a replacement for the one inside hls.js. It
 * answers three questions: which rendition should be stored, what files does it
 * consist of, and what manifest should be served back when there is no network.
 *
 * Pure over strings, so the byte-range arithmetic — the part that is wrong by
 * one and silently produces unplayable audio — is testable without a network.
 *
 * The audio-only rendition is the one that gets stored. That is not a shortcut:
 * this is audio mode, and on the reference stream the audio rendition is 12MB
 * against 27MB for the smallest video one. Downloading video for a podcast
 * would be storing something nobody is going to look at.
 */

export type AudioRendition = {
  /** Absolute URL of the audio-only media playlist. */
  url: string;
  /** From the master's EXT-X-MEDIA entry, for the manifest served back offline. */
  codecs: string;
  language: string;
  name: string;
};

export type MediaFile = {
  /** Absolute URL of the file the byte ranges are cut from. */
  url: string;
  /** Highest byte the playlist ever asks for, so a download knows when it is done. */
  lastByte: number;
};

/**
 * Find the audio-only rendition in a master playlist.
 *
 * Prefers the default audio group, which is the one a player would pick, and
 * falls back to the first. Returns null when the master has no separate audio
 * rendition — a muxed stream cannot be stored as audio alone, and pretending
 * otherwise would produce a download that plays video nobody asked for.
 */
export function findAudioRendition(
  master: string,
  masterUrl: string,
): AudioRendition | null {
  const entries = master
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.startsWith("#EXT-X-MEDIA:") && line.includes("TYPE=AUDIO"));

  if (entries.length === 0) return null;

  const chosen =
    entries.find((entry) => attribute(entry, "DEFAULT") === "YES") ?? entries[0]!;

  const uri = attribute(chosen, "URI");
  if (!uri) return null;

  return {
    url: absolute(uri, masterUrl),
    // Read off a variant rather than guessed. The audio entry itself carries no
    // CODECS attribute, and hls.js will not select a rendition whose codec it
    // was not told.
    codecs: audioCodecFor(master, attribute(chosen, "GROUP-ID") ?? "") ?? "mp4a.40.2",
    language: attribute(chosen, "LANGUAGE") ?? "en",
    name: attribute(chosen, "NAME") ?? "Audio",
  };
}

/**
 * The file a media playlist draws from, and how much of it is used.
 *
 * Handles both shapes. A playlist of separate segment files reports the one
 * file only when there is exactly one; a byte-range playlist — which is what
 * fragmented-MP4 streams produce, including the reference stream here — reports
 * the shared file and the highest byte any range reaches.
 *
 * `lastByte` rather than the file's Content-Length, because a playlist can
 * address part of a larger file and downloading the rest would be storing bytes
 * that will never be played.
 */
export function findMediaFile(playlist: string, playlistUrl: string): MediaFile | null {
  const lines = playlist.split("\n").map((line) => line.trim());

  let file: string | null = null;
  let lastByte = 0;
  let pendingRange: string | null = null;

  for (const line of lines) {
    if (line.startsWith("#EXT-X-MAP:")) {
      const uri = attribute(line, "URI");
      const range = attribute(line, "BYTERANGE");
      if (uri) file ??= uri;
      if (range) lastByte = Math.max(lastByte, rangeEnd(range, 0));
      continue;
    }

    if (line.startsWith("#EXT-X-BYTERANGE:")) {
      pendingRange = line.slice("#EXT-X-BYTERANGE:".length).trim();
      continue;
    }

    if (line.startsWith("#") || line === "") continue;

    // A URI line. Byte-range playlists repeat the same file on every one.
    file ??= line;
    if (file !== line) return null; // Separate segment files; not supported here.

    if (pendingRange) {
      lastByte = Math.max(lastByte, rangeEnd(pendingRange, lastByte));
      pendingRange = null;
    }
  }

  if (!file) return null;
  return { url: absolute(file, playlistUrl), lastByte };
}

/**
 * The master playlist to serve when there is no network.
 *
 * One variant, pointing at the stored audio rendition. Handing back the
 * original master offline would let the player choose a video rendition that
 * was never downloaded, and the failure would look like a broken download
 * rather than a missing one.
 */
export function buildOfflineMaster(
  rendition: AudioRendition,
  audioPlaylistUrl: string,
): string {
  return [
    "#EXTM3U",
    "#EXT-X-VERSION:6",
    "#EXT-X-INDEPENDENT-SEGMENTS",
    `#EXT-X-STREAM-INF:BANDWIDTH=128000,CODECS="${rendition.codecs}"`,
    audioPlaylistUrl,
    "",
  ].join("\n");
}

/** `bytes=start-end`, inclusive, as the Cache Storage layer needs it. */
export function parseRangeHeader(
  header: string | null,
  size: number,
): { start: number; end: number } | null {
  if (!header) return null;

  const match = /^bytes=(\d*)-(\d*)$/.exec(header.trim());
  if (!match) return null;

  const [, rawStart, rawEnd] = match;

  // "bytes=-500" means the last 500 bytes, not "up to byte 500". Getting this
  // backwards produces audio that plays the wrong part of the file.
  if (rawStart === "") {
    if (rawEnd === "") return null;
    const length = Number(rawEnd);
    return { start: Math.max(0, size - length), end: size - 1 };
  }

  const start = Number(rawStart);
  const end = rawEnd === "" ? size - 1 : Number(rawEnd);

  if (!Number.isFinite(start) || !Number.isFinite(end)) return null;
  if (start > end || start >= size) return null;

  return { start, end: Math.min(end, size - 1) };
}

function attribute(line: string, name: string): string | null {
  const match = new RegExp(`${name}=("([^"]*)"|([^,]*))`).exec(line);
  return match ? (match[2] ?? match[3] ?? null) : null;
}

/**
 * The audio codec for a group, taken from the first variant that references it.
 *
 * CODECS on a variant lists video first and audio second. Anything that is not
 * an `avc`/`hvc`/`av01` string is the audio one.
 */
function audioCodecFor(master: string, groupId: string): string | null {
  for (const line of master.split("\n")) {
    if (!line.startsWith("#EXT-X-STREAM-INF:")) continue;
    if (groupId && attribute(line, "AUDIO") !== groupId) continue;

    const codecs = attribute(line, "CODECS");
    if (!codecs) continue;

    const audio = codecs
      .split(",")
      .map((codec) => codec.trim())
      .find((codec) => !/^(avc|hvc|hev|av01|vp0)/.test(codec));

    if (audio) return audio;
  }
  return null;
}

/** `length@offset`, where a missing offset means "straight after the last one". */
function rangeEnd(range: string, previousEnd: number): number {
  const [rawLength, rawOffset] = range.split("@");
  const length = Number(rawLength);
  if (!Number.isFinite(length)) return previousEnd;

  const offset = rawOffset === undefined ? previousEnd : Number(rawOffset);
  return (Number.isFinite(offset) ? offset : previousEnd) + length;
}

function absolute(uri: string, base: string): string {
  return new URL(uri, base).toString();
}
