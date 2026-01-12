# Quick Deployment Guide

## 🚀 Deploy in 5 Minutes

### Step 1: Deploy Backend to Railway (2 min)

1. Go to [railway.app](https://railway.app) and sign in with GitHub
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your repository: `theperiodapp`
4. Railway will auto-detect Python
5. In project settings, set **Root Directory** to: `backend`
6. Go to **Variables** tab and add:

```env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
JWT_SECRET_KEY=your_32_char_secret_key
JWT_ALGORITHM=HS256
GEMINI_API_KEY=your_gemini_key
RAPIDAPI_KEY=your_rapidapi_key
CORS_ORIGINS=http://localhost:5173
```

7. Wait for deployment (2-3 minutes)
8. Copy your Railway URL (e.g., `https://xxx.up.railway.app`)

### Step 2: Deploy Frontend to Vercel (2 min)

1. Go to [vercel.com](https://vercel.com) and sign in with GitHub
2. Click **"Add New"** → **"Project"**
3. Import your repository: `theperiodapp`
4. Configure:
   - **Root Directory**: `frontend`
   - **Framework Preset**: Vite
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
5. Add environment variable:
   - Name: `VITE_API_BASE_URL`
   - Value: `https://your-railway-url.up.railway.app` (from Step 1)
6. Click **"Deploy"**
7. Wait for deployment (1-2 minutes)
8. Copy your Vercel URL (e.g., `https://xxx.vercel.app`)

### Step 3: Update CORS (1 min)

1. Go back to Railway dashboard
2. Go to your service → **Variables**
3. Update `CORS_ORIGINS`:
   ```
   https://your-vercel-url.vercel.app
   ```
4. Railway will auto-redeploy

### Step 4: Test (1 min)

1. Visit your Vercel URL
2. Try registering/logging in
3. Check browser console for errors
4. Test the app features

## ✅ Done!

Your app is now live:
- **Frontend**: `https://your-app.vercel.app`
- **Backend**: `https://your-app.railway.app`

## 🔄 Auto-Deployments

Both platforms auto-deploy on every push to `main` branch!

## 📚 Need More Details?

See `DEPLOYMENT.md` for detailed instructions and troubleshooting.










