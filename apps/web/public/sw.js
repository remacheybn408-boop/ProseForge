const CACHE = "proseforge-static-v1";
self.addEventListener("install", event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(["/", "/manifest.webmanifest"]))));
self.addEventListener("fetch", event => { const url = new URL(event.request.url); if (url.origin === self.location.origin && !url.pathname.startsWith("/api/")) event.respondWith(caches.match(event.request).then(hit => hit || fetch(event.request).then(response => { const copy = response.clone(); caches.open(CACHE).then(cache => cache.put(event.request, copy)); return response; }))); });
