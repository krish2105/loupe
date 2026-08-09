/*
  Service worker — ADR 0003's offline scope, and the honest half of it.

  What this does: keeps the app shell available offline, so opening Loupe with
  no connection shows the interface and a page explaining the state rather than
  the browser's dinosaur.

  What it deliberately does NOT do: cache media. ADR 0003 says offline downloads
  only work for content Loupe owns or that is openly licensed, and calls that a
  licensing fact rather than a technical gap. Every piece of media in the
  current catalogue is a third-party reference stream, so there is nothing here
  that may legitimately be cached, and caching it anyway to make a feature demo
  well would be the exact thing the ADR ruled out.

  When real owned media exists, segment caching goes here, gated on
  source_class = 'owned'.
*/

const SHELL = "loupe-shell-v1";

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
        Promise.all(keys.filter((key) => key !== SHELL).map((key) => caches.delete(key))),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;

  // Network-first for pages: the catalogue changes and a stale feed served from
  // cache while online would be worse than a slightly slower fresh one.
  if (request.mode !== "navigate") return;

  event.respondWith(
    fetch(request)
      .then((response) => {
        const copy = response.clone();
        caches.open(SHELL).then((cache) => cache.put(request, copy));
        return response;
      })
      .catch(() =>
        caches
          .match(request)
          .then((cached) => cached || caches.match("/offline")),
      ),
  );
});
