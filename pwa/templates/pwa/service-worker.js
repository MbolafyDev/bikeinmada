// ----- ZaraStore Service Worker (lecture offline des listes) -----
// Ce fichier est rendu par Django (Template), APP_VERSION vient de settings.APP_VERSION
const APP_VERSION = "{{ APP_VERSION }}";
const PRECACHE = `zarastore-precache-${APP_VERSION}`;
const RUNTIME  = `zarastore-runtime-${APP_VERSION}`;

// 1) Pré-cache : pages clés pour garantir un minimum de contenu offline
const PRECACHE_URLS = [
  "/",                 // liste commandes (ventes.urls sur root)
  "/offline/",
  "/ventes/",          // journal encaissement (si utile)
  "/articles/",
  "/achats/",
  "/stocks/",
  "/charges/",
  "/caisses/",
  "/livraison/",
  // Icônes PWA
  "/static/pwa/icons/icon-192.png",
  "/static/pwa/icons/icon-512.png",
  "/static/pwa/icons/maskable-512.png",
];

// --- Helpers ---
const isStatic = (req) =>
  req.destination === "style" ||
  req.destination === "script" ||
  req.destination === "image" ||
  new URL(req.url).pathname.startsWith("/static/");

// URL de listes/partials à mettre en "stale-while-revalidate"
// ⚠️ Ajuste si tu as d'autres chemins (ex: /.../liste/, /.../partial/, /.../htmx/)
const isListURL = (url) => {
  const p = url.pathname;
  return (
    // root = liste_commandes (ventes.urls)
    p === "/" ||
    p.startsWith("/ventes/") ||
    p.startsWith("/articles/") ||
    p.startsWith("/achats/") ||
    p.startsWith("/stocks/") ||
    p.startsWith("/charges/") ||
    p.startsWith("/caisses/") ||
    p.startsWith("/livraison/") ||
    // fragments génériques souvent utilisés
    p.endsWith("/partial/") ||
    p.includes("/htmx/")
  );
};

// --- Install / Activate ---
self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(PRECACHE).then((c) => c.addAll(PRECACHE_URLS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.map((k) =>
          // on garde seulement les caches courants
          (k.startsWith("zarastore-") && k !== PRECACHE && k !== RUNTIME)
            ? caches.delete(k)
            : null
        )
      )
    )
  );
  self.clients.claim();
});

// --- Fetch ---
self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Ne pas intercepter l'admin Django
  if (url.pathname.startsWith("/admin/")) return;

  // 0) Interdire POST en offline (pas d'API/queue ici)
  if (req.method === "POST" && !navigator.onLine) {
    event.respondWith(
      new Response(
        JSON.stringify({ ok: false, offline: true, message: "Hors ligne : enregistrement désactivé." }),
        { status: 503, headers: { "Content-Type": "application/json" } }
      )
    );
    return;
  }

  // 1) Navigations (HTML) -> network-first, puis cache, puis offline.html
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(RUNTIME).then((c) => c.put(req, copy));
          return res;
        })
        .catch(async () => (await caches.match(req)) || (await caches.match("/offline/")))
    );
    return;
  }

  // 2) Statiques -> cache-first
  if (isStatic(req)) {
    event.respondWith(
      caches.match(req).then(
        (cached) =>
          cached ||
          fetch(req).then((res) => {
            const copy = res.clone();
            caches.open(RUNTIME).then((c) => c.put(req, copy));
            return res;
          })
      )
    );
    return;
  }

  // 3) Listes & fragments (GET) -> stale-while-revalidate
  if (req.method === "GET" && isListURL(url)) {
    event.respondWith(
      caches.open(RUNTIME).then(async (cache) => {
        const cached = await cache.match(req);
        const network = fetch(req)
          .then((res) => {
            if (res && res.status === 200) cache.put(req, res.clone());
            return res;
          })
          .catch(() => null);
        return cached || network || new Response("", { status: 204 });
      })
    );
    return;
  }

  // 4) Par défaut -> network, fallback cache si déjà vu
  event.respondWith(
    fetch(req)
      .then((res) => {
        if (req.method === "GET" && res && res.status === 200) {
          const copy = res.clone();
          caches.open(RUNTIME).then((c) => c.put(req, copy));
        }
        return res;
      })
      .catch(() => caches.match(req))
  );
});
