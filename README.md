# MediaOne — PWA media hub (prototype)

Static HTML/CSS/JS app deployable on GitHub Pages. It uses Gutendex for Project Gutenberg books and Internet Archive metadata for media. No API secrets or backend.

## Deploy
Upload the **contents** of this folder to the repository root. In Settings → Pages choose Deploy from a branch → main → /(root). Open the Pages URL in iPhone Safari and choose Share → Add to Home Screen.

## Limitations
- This is an experimental MVP. Internet Archive query filters, licensing metadata, API availability, browser CORS and streaming support may vary. The application must not be treated as a fully licensed production catalog.
- Catalog may be empty if an upstream API blocks browser requests. There is no fallback to pirated sources.
- A work being downloadable does not guarantee that it is public domain in Ukraine. Verify item rights and territorial restrictions before public redistribution.
- Music and film playback require internet; the service worker caches only the app shell, not media.
- Favorites are localStorage and may disappear when Safari site data is cleared.
- No user accounts, background downloads, universal catalog, DRM bypass, or playback of subscription-only content.
- For production, audit licensing per item, improve accessibility, paginate APIs, handle source errors, and consider a proper data backend for caching/normalization.
