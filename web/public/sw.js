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

  // Network-first for media too, and that ordering matters more here than it
  // looks. A downloaded episode stores a rewritten master offering only the
  // audio rendition. Serving that while online would silently cap every stream
  // at audio quality, on a page showing a video player. Online gets the real
  // manifest; only a failed fetch falls back to what was stored.
  event.respondWith(
    (async () => {
      try {
        return await fetch(request);
      } catch (error) {
        // Only substitute a download when there actually is one. Returning a
        // synthetic error on a miss replaced every genuine network failure with
        // an indistinguishable one, which is how a browser-cache problem spent
        // an afternoon looking like a service-worker problem.
        const downloaded = await serveDownloaded(request);
        if (downloaded) return downloaded;
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
