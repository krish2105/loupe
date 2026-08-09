/*
  Service worker — ADR 0003's offline scope, and the honest half of it.

  Two jobs.

  The app shell: opening Loupe with no connection shows the interface and a
  page explaining the state rather than the browser's dinosaur.

  Downloaded audio: serving what the page put in Cache Storage, including
  cutting byte ranges out of it. HLS asks for a hundred ranges of one file, and
  Cache Storage matches on URL alone — so a ranged request would otherwise get
  the whole file back with a 200, which hls.js cannot use.

  The download itself happens in the page, not here. See download.ts.

  What is downloadable is decided by the database, not by this file: ADR 0003
  limits offline to content Loupe owns, and migration 0012 enforces it with a
  trigger.
*/

const SHELL = "loupe-shell-v1";
const MEDIA = "loupe-media-v1";

/*
  Exactly which media URLs have been downloaded.

  Held in memory because `event.respondWith` must be called synchronously, and
  looking in Cache Storage is async — so without this the worker has to decide
  whether to intervene before it knows whether it has anything, and the only
  way to do that is to intervene in everything.

  Intervening in everything is what broke playback. hls.js fetches a manifest
  and a hundred byte-ranges per episode, all cross-origin. Passing each one
  through `fetch(request)` inside the worker re-issues it from a different
  context, and this CDN sends `Vary: Origin, Access-Control-Request-Headers,
  Access-Control-Request-Method`, so responses are stored per header variant and
  the re-issued request can miss the variant and fail. The symptom was a player
  that attached, produced a blob URL, and then sat at readyState 0 forever with
  no error — because hls.js's own requests were failing, not the element.

  With this set, a request the worker has nothing for is never touched. The
  browser fetches it exactly as it would with no worker installed.
*/
let downloaded = new Set();

async function refreshDownloaded() {
  try {
    const cache = await caches.open(MEDIA);
    downloaded = new Set((await cache.keys()).map((request) => request.url));
  } catch {
    downloaded = new Set();
  }
}

// The page tells the worker when a download starts or is removed, so the set
// stays correct without polling.
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "downloads-changed") {
    event.waitUntil(refreshDownloaded());
  }
});

// Navigation requests only. Hashed build assets are handled by the browser's
// own HTTP cache, which is better at it than anything written here.
const PRECACHE = ["/", "/listen", "/offline"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            // Downloads are the person's data, not this worker's cache. Sweeping
            // them on activate would delete an episode someone saved for a
            // flight because a deploy happened.
            .filter((key) => key !== SHELL && key !== MEDIA)
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => refreshDownloaded())
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;

  if (request.mode === "navigate") {
    // Network-first: the catalogue changes, and a stale feed served from cache
    // while online is worse than a slightly slower fresh one.
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(SHELL).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(() =>
          caches.match(request).then((cached) => cached || caches.match("/offline")),
        ),
    );
    return;
  }

  if (request.method !== "GET") return;

  // Nothing downloaded for this URL: stay out of the way entirely. Not "fetch
  // and pass it through" — not intercepting at all, so the request is identical
  // to one made with no worker installed.
  if (!downloaded.has(request.url)) return;

  // Network-first even for a downloaded URL, and that ordering matters. A
  // downloaded episode stores a rewritten master offering only the audio
  // rendition; serving it while online would silently cap every stream at audio
  // quality on a page showing a video player. Online gets the real manifest,
  // and only a failed fetch falls back to what was stored.
  event.respondWith(
    (async () => {
      try {
        return await fetch(request);
      } catch (error) {
        const stored = await serveDownloaded(request);
        if (stored) return stored;
        throw error;
      }
    })(),
  );
});

async function serveDownloaded(request) {
  const cache = await caches.open(MEDIA);

  // Matched on URL rather than on the Request, because the Request carries the
  // Range header and the stored entry is the whole file.
  const stored = await cache.match(request.url);
  if (!stored) return null;

  const range = request.headers.get("range");
  if (!range) return stored;

  const body = await stored.arrayBuffer();
  const parsed = parseRange(range, body.byteLength);
  if (!parsed) {
    return new Response(null, {
      status: 416,
      headers: { "Content-Range": `bytes */${body.byteLength}` },
    });
  }

  const slice = body.slice(parsed.start, parsed.end + 1);

  return new Response(slice, {
    status: 206,
    headers: {
      "Content-Type": stored.headers.get("content-type") || "video/mp4",
      "Content-Length": String(slice.byteLength),
      "Content-Range": `bytes ${parsed.start}-${parsed.end}/${body.byteLength}`,
      "Accept-Ranges": "bytes",
    },
  });
}

/*
  Kept in step with parseRangeHeader in hls-manifest.ts, which is the tested
  copy. A service worker cannot import from the bundle, so this is duplicated
  rather than shared — and the duplication is the reason the other one has
  tests covering suffix ranges and open ends.
*/
function parseRange(header, size) {
  const match = /^bytes=(\d*)-(\d*)$/.exec(header.trim());
  if (!match) return null;

  const [, rawStart, rawEnd] = match;

  if (rawStart === "") {
    if (rawEnd === "") return null;
    return { start: Math.max(0, size - Number(rawEnd)), end: size - 1 };
  }

  const start = Number(rawStart);
  const end = rawEnd === "" ? size - 1 : Number(rawEnd);

  if (!Number.isFinite(start) || !Number.isFinite(end)) return null;
  if (start > end || start >= size) return null;

  return { start, end: Math.min(end, size - 1) };
}
