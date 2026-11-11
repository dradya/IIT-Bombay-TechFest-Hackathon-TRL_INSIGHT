# TRL INSIGHT — Frontend

React 19 + TypeScript (strict) + Vite 6 + Tailwind CSS v4 interface for the
TRL INSIGHT assessment platform.

## Commands

```bash
npm install        # install dependencies
npm run dev        # dev server on http://localhost:5173
npm run build      # tsc -b && vite build  ->  dist/
npm run preview    # preview the production build
```

## Proxy / API notes

- The app calls the API with **relative** `/api/...` paths (see
  `src/services/api.ts`) — no hardcoded host.
- In development, `vite.config.ts` proxies `/api` to `http://127.0.0.1:8000`,
  so the backend must be running:

  ```bash
  cd backend
  uvicorn app.main:app --reload --port 8000
  ```

- In production the FastAPI backend serves `frontend/dist` from the same
  origin (`backend/app/main.py`), so the relative paths and the `/api/docs`
  links work without any configuration.

## Structure

```
src/
  main.tsx, App.tsx       # entry + React Router routes
  index.css               # Tailwind v4 import + design tokens (@theme)
  layouts/AppLayout.tsx   # sidebar (desktop) / top bar + drawer (mobile)
  pages/                  # Overview, New Assessment, Assessment Result,
                          # History, Explorer, TRL Guide, Model Performance,
                          # Settings, 404
  components/             # StatCard, TrlScale, ConfidenceRing, EvidenceTable,
                          # StatusBadge, EmptyState, LoadingSpinner, ErrorBanner,
                          # ConfirmDialog, PageHeader, FilterBar, ConfidenceBar,
                          # Skeleton, Toast
  services/api.ts         # typed fetch wrapper (ApiError, downloadFile)
  hooks/useApi.ts         # generic GET loader (loading / error / refetch)
  types/index.ts          # interfaces mirroring the API JSON contract
  utils/format.ts         # percent / date / byte formatting helpers
```

All JSON field names are snake_case exactly as returned by the backend
(`docs/API_DOCUMENTATION.md`). Confidence values are 0–1 floats and are
rendered as percentages.
