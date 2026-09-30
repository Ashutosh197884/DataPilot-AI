# Deploying DataPilot AI — Live Demo for Judges

Two services, ~10 minutes, free tiers:

| Service | Host | What it needs |
|---|---|---|
| FastAPI backend | [Railway](https://railway.app) | Nothing (SQLite built in) |
| React frontend | [Vercel](https://vercel.com) | The Railway URL |

---

## 1. Backend on Railway

1. Go to [railway.app/new](https://railway.app/new) → **Deploy from GitHub repo** → pick `Ashutosh197884/DataPilot-AI`.
2. Railway detects the repo root. Set the **Root Directory** to `backend` (Settings → Source). The included `railway.json` + `Dockerfile` handle the rest.
3. No environment variables are required. Optional additions in **Variables**:
   - `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` — enables the Cloudinary asset/evidence layer and demo-asset upload.
   - `OPENAI_API_KEY` — optional phrasing enhancer only.
   - `CORS_ORIGINS` — set to `https://<your-vercel-domain>` (add it after step 2.4 below, then redeploy).
4. **Settings → Networking → Generate Domain** → note the URL, e.g. `https://datapilot-backend-production.up.railway.app`.
5. Verify: open `<railway-url>/health` → should return `{"status": "ok", ...}`.

> Railway injects `PORT`; the start command in `railway.json` uses it automatically.

## 2. Frontend on Vercel

1. Go to [vercel.com/new](https://vercel.com/new) → import `Ashutosh197884/DataPilot-AI`.
2. Set **Root Directory** to `frontend`. Framework preset: **Vite** (from `vercel.json`).
3. **Before deploying**, edit `frontend/vercel.json`: replace `REPLACE_WITH_RAILWAY_URL` with your Railway URL from step 1.4 (no trailing slash), e.g.:
   ```json
   { "source": "/api/(.*)", "destination": "https://datapilot-backend-production.up.railway.app/api/$1" }
   ```
   Commit + push (or paste the edit in Vercel's editor). This routes `/api/*` to the backend.
4. Deploy. Note the domain, e.g. `https://datapilot-ai.vercel.app`.
5. Go back to Railway → backend **Variables** → `CORS_ORIGINS=https://datapilot-ai.vercel.app` → redeploy. (The `/api` proxy avoids CORS for API calls, but the backend allows the Vercel origin explicitly for SSE EventSource.)

## 3. Judge-ready checks

- [ ] `<vercel-url>` loads the workspace
- [ ] Run the Haryana query → workflow streams live → dashboard opens
- [ ] **Explain Result** → calculation modal
- [ ] **View Evidence** → full chain incl. dataset + source
- [ ] `<railway-url>/health` returns ok

## Troubleshooting

| Symptom | Fix |
|---|---|
| `/api/...` 404 on Vercel | `vercel.json` rewrite still says `REPLACE_WITH_RAILWAY_URL` |
| CORS error in console | Set `CORS_ORIGINS` on Railway to the exact Vercel origin (scheme + domain, no trailing slash) |
| Backend sleeping/crashed | Railway free tier: check Deploy Logs; restart policy is ON_FAILURE ×3 |
| SSE not streaming | Ensure the Railway domain is used via the Vercel proxy (`/api/...`), not cross-origin fetches |
