# PeriodCycle.AI

FastAPI backend (cycle logic, Supabase) and optional Vite frontend. Production backend is deployed on **Railway** (see `railway.json`).

## Developer setup

### Prerequisites

- Python 3.11+ (recommended)
- Node.js 18+ (if you run the frontend)

### Backend (API)

From the repository root:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copy `backend/.env.example` to `backend/.env` and set `SUPABASE_URL`, `SUPABASE_KEY`, and **`JWT_SECRET_KEY`** (or **`SUPABASE_JWT_SECRET`**) to the **Supabase JWT secret** (Dashboard → Project Settings → API → JWT Secret). The API verifies Supabase Auth access tokens (HS256) with that value. Optional: **`CORS_ORIGINS`** (comma-separated) and **`CORS_EXTRA_ORIGIN`** for your Flutter web or deployed frontend URL; **`CORS_ORIGIN_REGEX`** defaults to Vercel + Railway host patterns.

Run the API (reload for local dev):

```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- API: [http://localhost:8000](http://localhost:8000)
- OpenAPI docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Frontend (optional)

In a **second** terminal:

```bash
cd frontend
npm install
npm run dev
```

- Dev server: [http://localhost:5173](http://localhost:5173)  
- Optional: copy `frontend/.env.local.example` to `frontend/.env.local` if you need a non-default API URL.

### Dependencies

- Canonical Python dependencies live in **`backend/requirements.txt`**.
- The root **`requirements.txt`** only includes that file so tools that expect a root manifest (e.g. some hosts) stay in sync.

### Railway (backend)

`railway.json` sets the start command to run Uvicorn from `backend`. Configure environment variables in the Railway project dashboard; do not commit secrets.

### Supabase Auth + `/auth/register`

After the user signs up in **Supabase Auth**, call `POST /auth/register` with the same JSON body as before and include **`Authorization: Bearer <supabase_access_token>`**. The backend verifies the token, sets `users.id` to the JWT **`sub`** (same UUID as `auth.users`), and checks that the registration **email** matches the token’s **email** claim when present. Duplicate accounts are still prevented by the unique **email** constraint.
