// Keeps the site looking the same when the internet is off. Pages and styles come from the device;
// requests to the server (paths under /v1/) always go to the network, so the page can show its own
// "no internet" message. Served from the site root so that it controls every page (see main.py).
const CACHE = "zaban-shell-v1";
const SHELL = [
  "/static/vendor/bootstrap/bootstrap.rtl.min.css",
  "/static/vendor/bootstrap/bootstrap.min.css",
  "/static/vendor/fonts/fonts.css",
  "/static/css/app.css",
  "/static/js/common.js",
  "/static/offline.html",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => Promise.all(SHELL.map((path) => cache.add(path).catch(() => null))))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(names.filter((name) => name !== CACHE).map((name) => caches.delete(name))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  // Only the site's own GET requests are kept. Server data is never cached.
  if (request.method !== "GET" || url.origin !== self.location.origin || url.pathname.includes("/v1/")) return;
  event.respondWith(networkFirst(request));
});

async function networkFirst(request) {
  const cache = await caches.open(CACHE);
  try {
    const response = await fetch(request);
    if (response.ok) cache.put(request, response.clone());
    return response;
  } catch (_) {
    const saved = await cache.match(request);
    if (saved) return saved;
    if (request.mode === "navigate") {
      const offline = await cache.match("/static/offline.html");
      if (offline) return offline;
    }
    return Response.error();
  }
}
