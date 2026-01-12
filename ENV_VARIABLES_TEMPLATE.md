# Environment Variables Template

Copy these and fill in your actual values when deploying.

## 🔐 Backend Environment Variables (Railway)

```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlvdXItcmVmIiwiYXVkIjoiYW5vbiIsImlhdCI6MTY0NTk2NjQwMCwiZXhwIjoxOTYxNTQyNDAwfQ.your-anon-key
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.your-service-role-key
JWT_SECRET_KEY=your-32-character-minimum-secret-key-change-this
JWT_ALGORITHM=HS256
GEMINI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
RAPIDAPI_KEY=your-rapidapi-key-here
CORS_ORIGINS=http://localhost:5173
```

**After frontend is deployed, update:**
```env
CORS_ORIGINS=https://your-vercel-app.vercel.app
```

## 🌐 Frontend Environment Variable (Vercel)

```env
VITE_API_BASE_URL=https://your-railway-app.up.railway.app
```

**Note**: Set this AFTER backend is deployed and you have the Railway URL.

---

## 📝 How to Get These Values

### Supabase Keys
1. Go to https://supabase.com
2. Select your project
3. Go to **Settings** → **API**
4. Copy:
   - **Project URL** → `SUPABASE_URL`
   - **anon public** key → `SUPABASE_KEY`
   - **service_role** key → `SUPABASE_SERVICE_ROLE_KEY`

### JWT Secret Key
Generate a secure random string (minimum 32 characters):
```bash
openssl rand -hex 32
```

### Gemini API Key
1. Go to https://makersuite.google.com/app/apikey
2. Create an API key
3. Copy to `GEMINI_API_KEY`

### RapidAPI Key
1. Go to https://rapidapi.com
2. Sign up / Sign in
3. Go to your API subscriptions
4. Copy your API key → `RAPIDAPI_KEY`






