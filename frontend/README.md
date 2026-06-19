# CloneLM frontend

React + TypeScript + Vite, styled with Tailwind CSS v4. Phase 0b skeleton: the
designed three-pane shell (Quellen / Chat / Studio) in its empty state, a typed
API client, and a backend health indicator. Phase 3 (Track C) builds the full
UX on top.

```bash
npm install
npm run dev      # http://localhost:5173 (proxies /api and /health to :8000)
npm run build    # tsc -b && vite build  (type-checks + production bundle)
```

- API contract types: `src/api/types.ts` (mirror of the backend JSON).
- Typed client: `src/api/client.ts`.
- Design source of truth: `../design/CloneLM-*.excalidraw`. UI copy is German.
