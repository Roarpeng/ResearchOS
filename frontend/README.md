# ResearchOS Frontend (Research Console MVP)

Minimal Vite + React console for Phase 4 demos.

## Features

- Brand-first ResearchOS landing of the console
- Create research task form (`POST /api/v1/research/tasks`)
- Plan / Evidence / Result panels
- Talks to Gateway at `http://localhost:8000` (dev proxy `/api`)

## Run

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

Optional: set gateway explicitly

```bash
VITE_GATEWAY_URL=http://localhost:8000 npm run dev
```

## Build

```bash
npm run build
npm run preview
```

## Notes

- Requires Phase 2 Gateway for live task create/status.
- Without Gateway, the UI still loads and surfaces a clear connection error.
- Design fonts: IBM Plex Sans + Source Serif 4; teal/ink palette (not purple-default).
