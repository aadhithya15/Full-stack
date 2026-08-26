# HueFit Backend — Deployment Guide

> For anyone deploying this service. No code changes are needed — the app is
> configured entirely through environment variables. If a step here fails,
> check the Troubleshooting table at the end.

## What this service is
Flask REST API (Python) for the HueFit AI fashion stylist.
- Database/Auth/Storage: **Supabase** (already hosted — you only need the keys)
- AI providers: **Google Gemini** (primary) + **Groq** (fallback) — free-tier keys
- Outfit images: Pollinations.ai (no key needed)
- All endpoints under `/api/*`; health check at `GET /api/health`

## Prerequisites (accounts/keys the deployer must have)
| Item | Where it comes from |
|---|---|
| `SUPABASE_URL` | Supabase project -> Settings -> API -> Project URL |
| `SUPABASE_SERVICE_KEY` | Same page -> service_role key (NOT the anon key) |
| `SUPABASE_JWT_SECRET` | Settings -> JWT Keys -> Legacy JWT Secret |
| `GEMINI_API_KEY` | https://aistudio.google.com -> Get API key (free) |
| `GROQ_API_KEY` | https://console.groq.com -> API Keys (free) |

Notes:
- The Supabase project must already have the schema applied. If it is a FRESH
  Supabase project: run `migrations/001_init.sql` once in the Supabase SQL
  Editor, and disable Authentication -> Sign In / Providers -> Email ->
  "Confirm email". The storage bucket `user-uploads` is auto-created on first use.
- If AI keys are missing/invalid, the API still runs in MOCK MODE (sample
  recommendations, `"mock": true` in responses). Nothing crashes.

## Option A — Deploy to Render (recommended, ~15 min, free)
1. Fork/have this repo on GitHub.
2. https://render.com -> New + -> **Blueprint** -> select this repo.
   `render.yaml` is auto-detected and configures everything:
   - build: `pip install -r requirements.txt`
   - start: `gunicorn "app:create_app()" -b 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120`
   - health check: `/api/health`, Python 3.12.7, free plan
3. In the service -> **Environment** tab: set the 5 secret vars from the table
   above (render.yaml marks them `sync: false` so they are never in the repo).
4. Set `ALLOWED_ORIGINS` to the frontend's exact origin(s), comma-separated,
   no trailing slash. Example:
   `http://localhost:5173,https://huefit.vercel.app`
5. Deploy. First build takes 3-6 min.
6. Verify: `python check_deploy.py https://YOUR-SERVICE.onrender.com`
   (or just open `https://YOUR-SERVICE.onrender.com/api/health` — expect
   `"status": "ok"`, `"supabase_configured": true`, `"ai_mock_mode": false`).
7. Free tier sleeps after ~15 min idle (30-60 s cold start). Optional fix:
   point a free UptimeRobot monitor at `/api/health` every 5 minutes.

## Option B — Run on any server / locally
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # fill in the 5 secrets listed above
python run.py                    # dev server on :5000
# production:
gunicorn "app:create_app()" -b 0.0.0.0:5000 --workers 1 --threads 4 --timeout 120
```
Python 3.12+ recommended (3.14 works; pillow>=11.3 required for it).

## Environment variables (complete reference)
| Var | Required | Default | Purpose |
|---|---|---|---|
| SUPABASE_URL | yes | - | Supabase project URL (https://xxx.supabase.co, no path) |
| SUPABASE_SERVICE_KEY | yes | - | service_role key (server-side only, bypasses RLS) |
| SUPABASE_JWT_SECRET | yes | - | present for completeness; token checks go through Supabase |
| GEMINI_API_KEY | no* | placeholder | primary AI; *mock mode if absent |
| GROQ_API_KEY | no* | placeholder | fallback AI; *mock mode if both absent |
| ALLOWED_ORIGINS | yes (prod) | http://localhost:5173 | CORS allowlist, comma-separated exact origins |
| FLASK_ENV | no | development | set `production` when deployed |
| PORT | no | 5000 | listen port (Render injects its own) |
| MAX_UPLOAD_MB | no | 5 | photo upload size cap |

## How to verify a deployment (in order)
1. `GET /api/health` -> `status: ok`, `supabase_configured: true`
2. `POST /api/auth/register` with `{email, password, full_name}` -> 201 + token
3. `POST /api/fashion/analyze` (multipart: `skin_tone_text`, `occasion`,
   Bearer token) -> 3-5 recommendations with hex colours and image URLs
4. `GET /api/auth/me` without a token -> 401 with
   `{"success": false, "error": {"code": "UNAUTHORIZED", ...}}`
   (confirms auth + unified error format)
Automated version of all this: `python check_deploy.py <base-url>`.

## Operational notes
- Rate limits are built in: login/register 5/min/IP, analyze 8/min/user,
  save 30/min/user. 429 responses include a retry hint.
- AI calls take 5-20 s; the gunicorn timeout is 120 s for this reason. Do not
  lower it.
- Logs print one line per request (method, path, status, ms) and log which AI
  provider/model served each recommendation set.
- Scaling beyond one instance: the in-memory rate limiter is per-process;
  swap its store for Redis (see `app/middleware/rate_limit.py`) when adding
  workers/instances.

## Troubleshooting
| Symptom | Cause / fix |
|---|---|
| health shows `supabase_configured: false` | env vars missing or placeholder values |
| health shows `ai_mock_mode: true` | AI keys missing/typo'd (app still works, mock content) |
| PGRST205 "table not found" errors | migrations/001_init.sql was not run on this Supabase project |
| Browser CORS errors | ALLOWED_ORIGINS missing the exact frontend origin (scheme + host, no trailing slash) |
| 403 not_admin in logs | anon key was used instead of service_role key |
| Registration returns needs_email_confirmation | disable "Confirm email" in Supabase Auth settings |
| First request takes ~60 s | free-tier cold start; add an UptimeRobot ping |
