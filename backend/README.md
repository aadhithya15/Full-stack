# HueFit API — Backend

> **HueFit** — *Your colours. Your fit.*
> AI personal fashion stylist: analyzes your skin tone (from a photo or a
> description), your occasion and preferences, and generates personalized
> outfit recommendations — colours with hex codes, accessories, footwear,
> styling tips and AI-generated outfit images.

## Features

- **Email/password authentication** (Supabase Auth, JWT bearer tokens)
- **AI outfit recommendations** — Google Gemini (primary) with Groq fallback,
  automatic model discovery, strict-JSON validation and retries; falls back to
  a built-in mock stylist if no AI keys are configured (the app always works)
- **Photo skin-tone detection** — Gemini Vision with a Pillow pixel-analysis
  fallback (works even when the vision API is unavailable)
- **Outfit images** — generated free via Pollinations.ai (no API key needed)
- **Anti-repetition** — the backend remembers each user's recent outfits and
  automatically excludes them ("Generate More" never repeats)
- **Saved looks / wardrobe** — save, favourite, list and delete outfits
- **Profile & preferences** — skin tone, style, budget, language
- **Rate limiting** — login/register 5/min/IP, analyze 8/min/user
- **Unified error format** on every endpoint
- **70+ automated tests** (hermetic — no network or keys needed to run them)

## Tech Stack

| Layer | Technology |
|---|---|
| API | Python 3.12+ / Flask + gunicorn |
| Database, Auth, Storage | Supabase (PostgreSQL, RLS enabled) |
| AI (text) | Gemini 2.x/3.x flash (primary), Groq (fallback) |
| AI (vision) | Gemini Vision + Pillow fallback |
| Outfit images | Pollinations.ai |
| Deployment | Render (config in `render.yaml`) — see `DEPLOYMENT.md` |

## Quick Start (local)

```bash
# 1. clone and enter
git clone <this-repo-url>
cd huefit-backend

# 2. virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows  (Mac/Linux: source .venv/bin/activate)

# 3. dependencies
pip install -r requirements.txt

# 4. configuration
copy .env.example .env          # Mac/Linux: cp .env.example .env
# fill in the Supabase values (see below); AI keys are optional (mock mode)

# 5. run
python run.py                   # -> http://localhost:5000
```

Verify: open http://localhost:5000/api/health — expect `"status": "ok"`.

### Environment variables (`.env`)

| Variable | Required | Purpose |
|---|---|---|
| `SUPABASE_URL` | yes | Supabase project URL (`https://xxx.supabase.co`) |
| `SUPABASE_SERVICE_KEY` | yes | service_role key (Settings → API) |
| `SUPABASE_JWT_SECRET` | yes | Settings → JWT Keys → Legacy JWT Secret |
| `GEMINI_API_KEY` | no* | free key from aistudio.google.com |
| `GROQ_API_KEY` | no* | free key from console.groq.com |
| `ALLOWED_ORIGINS` | prod only | comma-separated frontend origins (CORS) |

\* Without AI keys the API runs in **mock mode**: identical response shapes
with sample content and `"mock": true` — the full app remains testable.

### First-time Supabase setup

1. Create a free project at supabase.com
2. SQL Editor → run `migrations/001_init.sql` (creates all tables, triggers, RLS)
3. Authentication → Sign In / Providers → Email → disable **"Confirm email"**
4. Copy the three keys into `.env`

Verify each layer with the included checkers:

```bash
python check_supabase.py   # DB tables + storage bucket
python check_auth.py       # live register/login/token round-trip
python check_ai.py         # real AI recommendation (needs a key)
python check_photo.py      # skin-tone detection pipeline
```

## API Overview

Base URL: `http://localhost:5000/api` — full request/response details in
`docs/API-CONTRACT.md` (if present) or the route files.

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | – | service status + config state |
| POST | `/auth/register` | – | create account → JWT |
| POST | `/auth/login` | – | sign in → JWT |
| GET | `/auth/me` | ✅ | current user + profile |
| POST | `/auth/logout` | ✅ | logout (client discards token) |
| POST | `/fashion/analyze` | ✅ | **main feature** — multipart form (photo or `skin_tone_text`, `occasion`, optional gender/style/budget/weather/notes/`exclude`) → 3–5 outfit recommendations |
| GET | `/fashion/history` | ✅ | past analyses |
| POST | `/fashion/save` | ✅ | save a recommendation |
| GET | `/fashion/saved` | ✅ | wardrobe (full outfits embedded) |
| PATCH | `/fashion/saved/:id` | ✅ | toggle favourite |
| DELETE | `/fashion/saved/:id` | ✅ | remove saved look |
| GET | `/profile` | ✅ | profile + preferences |
| PUT | `/profile` | ✅ | update preferences |

Auth: send `Authorization: Bearer <token>` on protected endpoints.

Every error, from any endpoint, has the same shape:

```json
{ "success": false, "error": { "code": "INVALID_INPUT", "message": "Occasion is required" } }
```

Codes: `INVALID_INPUT` 400 · `UNAUTHORIZED` 401 · `FORBIDDEN` 403 ·
`NOT_FOUND` 404 · `FILE_TOO_LARGE` 413 · `RATE_LIMITED` 429 ·
`AI_UNAVAILABLE` 502 · `SERVER_ERROR` 500

## Project Structure

```
huefit-backend/
├── app/
│   ├── __init__.py            # app factory: CORS, logging, error handlers
│   ├── config.py              # env config + mock-mode detection
│   ├── routes/                # health, auth, fashion, profile endpoints
│   ├── services/              # auth, AI (real + mock), skin tone, images, storage
│   ├── db/                    # Supabase client + all queries (ownership enforced)
│   ├── middleware/            # @require_auth, rate limiter
│   └── utils/                 # unified errors, validators
├── migrations/001_init.sql    # full database schema
├── tests/                     # 70+ hermetic tests (pytest -q)
├── check_*.py                 # live diagnostic scripts per subsystem
├── run.py                     # dev entry point
├── render.yaml / Procfile     # deployment config
├── DEPLOYMENT.md              # step-by-step deployment guide
└── .env.example               # documented configuration template
```

## Tests

```bash
pytest -q
```

Tests are hermetic: AI keys are forced to placeholders and all external
calls are mocked, so the suite runs offline, free, and deterministic.

## Deployment

See **`DEPLOYMENT.md`** — covers Render (one-click via `render.yaml`),
generic servers, the complete env-var reference, verification steps and
troubleshooting. Runs entirely on free tiers (Render + Supabase + Gemini/Groq).

## Security Notes

- `.env` is gitignored — secrets never enter the repository
- Supabase Row Level Security enabled on all tables; the API additionally
  enforces per-user ownership in every query (foreign IDs return 404)
- Passwords handled by Supabase Auth (bcrypt); tokens validated server-side
- Uploaded photos stored in a private bucket, served via signed URLs only
```
