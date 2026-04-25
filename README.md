# PeriodCycle.AI

PeriodCycle.AI is a cycle tracking product with:

- a FastAPI backend in `backend/` (core business logic and API),
- SQL schema/migrations in `database/`,
- and an optional Vite + React frontend in `frontend/`.

The production backend is intended to run on Railway.

## Repository layout

```text
.
├── backend/            # FastAPI app, routes, services, prediction logic
├── database/           # schema.sql + migration SQL files
├── frontend/           # optional web client (Vite + React)
├── railway.json        # Railway deploy config
├── Procfile            # process fallback/start command
└── requirements.txt    # delegates to backend/requirements.txt
```

## Tech stack

### Backend

- Python 3.11+
- FastAPI + Uvicorn
- Supabase (database + auth ecosystem)
- `python-jose` for JWT verification/signing
- `passlib[argon2]` for password hashing
- APScheduler for notification jobs
- Google GenAI SDK for AI chat

### Frontend (optional)

- Vite
- React
- Tailwind CSS

## Prerequisites

- Python 3.11+ (recommended)
- Node.js 18+ (required only for frontend work)
- A Supabase project with schema applied
- Optional: Gemini API key, SMTP credentials, Firebase service account

## Quick start

### 1) Clone and enter repo

```bash
git clone <your-repo-url>
cd PROJECT2
```

### 2) Backend setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create local env file:

```bash
cp .env.example .env
```

Run API:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Available URLs:

- API: [http://localhost:8000](http://localhost:8000)
- OpenAPI docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health: [http://localhost:8000/health](http://localhost:8000/health)

### 3) Frontend setup (optional)

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

- Frontend dev URL: [http://localhost:5173](http://localhost:5173)

## Environment variables

Use `backend/.env.example` as the source template.

### Required backend env vars

- `SUPABASE_URL`
- `SUPABASE_KEY` (or `SUPABASE_ANON_KEY` fallback)
- `JWT_SECRET_KEY` (or `SUPABASE_JWT_SECRET`)

### Strongly recommended for production

- `SUPABASE_SERVICE_ROLE_KEY` (only where needed server-side)
- `ENV=production`
- `CORS_ORIGINS` (explicit allowed origins)
- `CORS_ORIGIN_REGEX` (if you use wildcard host patterns)
- `GEMINI_API_KEY` (if AI chat is enabled)
- `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `FROM_EMAIL` (if email is enabled)
- `FIREBASE_CREDENTIALS_PATH` (if push notifications are enabled)

### Auth/JWT notes

- Supabase Auth access tokens are verified using HS256.
- `JWT_SECRET_KEY` must match your Supabase JWT secret.
- `/auth/register` can optionally accept a Supabase bearer token and bind `users.id` to token `sub`.

## Running services locally

### Backend only (mobile/backend development)

```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Backend + frontend

Terminal 1:

```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Terminal 2:

```bash
cd frontend
npm run dev
```

## Core backend modules

- `backend/main.py`: app creation, middleware, router registration, startup/shutdown lifecycle.
- `backend/database.py`: Supabase clients and retry wrappers.
- `backend/auth_utils.py`: password hash + JWT utilities.
- `backend/routes/`: API routes:
  - `auth.py`, `user.py`, `periods.py`, `cycles.py`,
  - `wellness.py`, `ai_chat.py`, `feedback.py`, `meta.py`, `debug.py`.
- `backend/notification_service.py`: scheduled notification workflow.
- `backend/push_notification_service.py`: Firebase push dispatch helper.

## Database management

- Canonical schema: `database/schema.sql`
- Incremental SQL changes: `database/migrations/` and root SQL files in `database/`
- Migration context doc: `database/COMPLETE_MIGRATION_GUIDE.md`

Recommended workflow:

1. Apply schema/migration SQL in a non-production environment first.
2. Validate API behavior (especially auth/cycle endpoints).
3. Promote same SQL to production.
4. Keep migration files immutable after deploy.

## Deployment (Railway)

This repo includes:

- `railway.json` with start command:
  - `uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}`
- `Procfile` fallback:
  - `web: cd backend && uvicorn main:app --host=0.0.0.0 --port=${PORT}`

Deployment checklist:

1. Set all required env vars in Railway.
2. Ensure `ENV=production`.
3. Set strict CORS values (avoid wildcard origins).
4. Verify `/health` after deploy.
5. Smoke test auth + period logging endpoints from mobile app.

## Developer workflows

### Install dependencies

- Python dependencies are canonical in `backend/requirements.txt`.
- Root `requirements.txt` delegates to backend manifest for host/tool compatibility.
- Frontend dependencies are managed via `frontend/package.json`.

### Linting

- Frontend lint:

```bash
cd frontend
npm run lint
```

### API exploration

- Use FastAPI docs at `/docs` for request/response schemas and manual testing.

## Operational notes

- Notification scheduler starts on app boot if APScheduler/service imports succeed.
- `/debug` diagnostics are blocked in production mode by route guard logic.
- Security headers are added in middleware (`X-Frame-Options`, `X-Content-Type-Options`, HSTS).
- CORS behavior is environment-driven; production should use explicit trusted origins.

## Troubleshooting

### API fails on startup with Supabase errors

- Check `SUPABASE_URL` and `SUPABASE_KEY`.
- Confirm variables are loaded in `backend/.env`.

### Auth fails with token errors

- Verify `JWT_SECRET_KEY`/`SUPABASE_JWT_SECRET` matches Supabase JWT secret.
- Ensure client sends `Authorization: Bearer <token>`.

### AI endpoints fail

- Confirm `GEMINI_API_KEY` is set.
- Watch logs for quota/rate-limit responses (429 handling exists in backend).

### Push/email not sending

- Push requires valid Firebase admin credentials file path.
- Email requires SMTP credentials; missing values will skip sends.

## Security and secrets

- Never commit secrets in `.env` files.
- Keep service-role and JWT secrets only in secret managers (Railway/Supabase secure config).
- Rotate credentials if accidentally exposed.

## Gaps to be aware of

- Automated backend test coverage and CI workflow are currently limited/not fully established in this repo.
- Before production hardening, prioritize adding:
  - integration tests,
  - CI checks,
  - rate limiting on sensitive endpoints.

## Contributing guidelines (recommended)

When making backend changes:

1. Keep route responses backward compatible for mobile clients.
2. Update SQL migrations and docs together when schema changes.
3. Validate `/health`, `/auth`, `/periods`, and `/cycles` flows before merge.
4. Update this README when setup/deploy/runtime behavior changes.
