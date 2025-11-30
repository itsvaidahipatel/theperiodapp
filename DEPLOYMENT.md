# Deployment Guide

This guide explains how to deploy the Period GPT2 application to Vercel (frontend) and Railway (backend).

## Prerequisites

- GitHub account with the repository
- Vercel account (free tier available)
- Railway account (free tier available)
- All environment variables configured

---

## 🚀 Frontend Deployment (Vercel)

### Option 1: Deploy via Vercel Dashboard (Recommended)

1. **Go to Vercel Dashboard**
   - Visit [vercel.com](https://vercel.com)
   - Sign in with GitHub

2. **Import Project**
   - Click "Add New" → "Project"
   - Import your GitHub repository
   - Select the repository: `theperiodapp`

3. **Configure Project**
   - **Root Directory**: `frontend`
   - **Framework Preset**: Vite
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
   - **Install Command**: `npm install`

4. **Environment Variables**
   Add the following environment variable:
   ```
   VITE_API_BASE_URL=https://your-railway-backend-url.railway.app
   ```
   (Replace with your actual Railway backend URL after backend deployment)

5. **Deploy**
   - Click "Deploy"
   - Wait for build to complete
   - Your frontend will be live at `https://your-project.vercel.app`

### Option 2: Deploy via Vercel CLI

```bash
# Install Vercel CLI
npm i -g vercel

# Navigate to frontend directory
cd frontend

# Login to Vercel
vercel login

# Deploy
vercel

# Set environment variable
vercel env add VITE_API_BASE_URL
# Enter: https://your-railway-backend-url.railway.app

# Deploy to production
vercel --prod
```

---

## 🚂 Backend Deployment (Railway)

### Step 1: Create Railway Project

1. **Go to Railway Dashboard**
   - Visit [railway.app](https://railway.app)
   - Sign in with GitHub

2. **Create New Project**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository: `theperiodapp`

3. **Configure Service**
   - Railway will auto-detect it's a Python project
   - **Root Directory**: `backend`
   - Railway will use the `Procfile` or `railway.json` for configuration

### Step 2: Set Environment Variables

In Railway dashboard, go to your service → Variables tab and add:

```env
# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# JWT
JWT_SECRET_KEY=your_jwt_secret_key_minimum_32_characters
JWT_ALGORITHM=HS256

# API Keys
GEMINI_API_KEY=your_gemini_api_key
RAPIDAPI_KEY=your_rapidapi_key

# CORS (Important!)
CORS_ORIGINS=https://your-vercel-frontend-url.vercel.app,https://your-custom-domain.com
```

**Important**: 
- Add your Vercel frontend URL to `CORS_ORIGINS` after frontend is deployed
- Separate multiple origins with commas (no spaces)

### Step 3: Deploy

1. Railway will automatically detect changes and deploy
2. Or click "Deploy" in the dashboard
3. Wait for deployment to complete
4. Your backend will be live at `https://your-project.railway.app`

### Step 4: Get Backend URL

1. Go to your Railway service
2. Click on the service
3. Go to "Settings" → "Networking"
4. Generate a public domain or use the provided Railway domain
5. Copy the URL (e.g., `https://your-project.up.railway.app`)

---

## 🔄 Update Frontend with Backend URL

After backend is deployed:

1. **Go to Vercel Dashboard**
2. **Select your project**
3. **Go to Settings → Environment Variables**
4. **Update `VITE_API_BASE_URL`**:
   ```
   VITE_API_BASE_URL=https://your-railway-backend-url.railway.app
   ```
5. **Redeploy** the frontend (or it will auto-redeploy on next push)

---

## 🔄 Update Backend CORS

After frontend is deployed:

1. **Go to Railway Dashboard**
2. **Select your backend service**
3. **Go to Variables**
4. **Update `CORS_ORIGINS`**:
   ```
   CORS_ORIGINS=https://your-vercel-frontend-url.vercel.app
   ```
5. **Redeploy** the backend (Railway will auto-redeploy)

---

## ✅ Verification

### Test Backend
```bash
curl https://your-railway-backend-url.railway.app/health
# Should return: {"status":"healthy"}
```

### Test Frontend
- Visit your Vercel URL
- Check browser console for any CORS errors
- Try logging in/registering

---

## 🔧 Troubleshooting

### CORS Errors
- Ensure `CORS_ORIGINS` in Railway includes your Vercel URL
- Check for trailing slashes in URLs
- Verify environment variables are set correctly

### Backend Not Starting
- Check Railway logs for errors
- Verify all environment variables are set
- Ensure `Procfile` is in the `backend/` directory

### Frontend Build Fails
- Check Vercel build logs
- Verify `VITE_API_BASE_URL` is set
- Ensure all dependencies are in `package.json`

### Database Connection Issues
- Verify Supabase credentials are correct
- Check Supabase project is active
- Ensure Supabase allows connections from Railway IPs

---

## 📝 Environment Variables Summary

### Frontend (Vercel)
- `VITE_API_BASE_URL` - Backend API URL

### Backend (Railway)
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_KEY` - Supabase anon key
- `SUPABASE_SERVICE_ROLE_KEY` - Supabase service role key
- `JWT_SECRET_KEY` - JWT secret (min 32 chars)
- `JWT_ALGORITHM` - JWT algorithm (HS256)
- `GEMINI_API_KEY` - Google Gemini API key
- `RAPIDAPI_KEY` - RapidAPI key
- `CORS_ORIGINS` - Allowed frontend origins (comma-separated)

---

## 🚀 Continuous Deployment

Both Vercel and Railway support automatic deployments:
- **Vercel**: Auto-deploys on push to `main` branch
- **Railway**: Auto-deploys on push to `main` branch

Just push to GitHub and both will automatically redeploy!

---

## 📞 Support

If you encounter issues:
1. Check deployment logs in Vercel/Railway dashboards
2. Verify all environment variables are set
3. Check CORS configuration matches your frontend URL
4. Ensure database is accessible from Railway





