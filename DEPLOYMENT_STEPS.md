# Step-by-Step Deployment Guide

Follow these steps in order to deploy your app.

## 📋 Pre-Deployment Checklist

- [ ] Code is pushed to GitHub
- [ ] You have accounts for:
  - [ ] Railway (https://railway.app) - Sign up with GitHub
  - [ ] Vercel (https://vercel.com) - Sign up with GitHub
- [ ] You have your environment variables ready (see below)

---

## 🚂 STEP 1: Deploy Backend to Railway

### 1.1 Create Railway Project

1. Go to **https://railway.app**
2. Sign in with **GitHub**
3. Click **"New Project"**
4. Select **"Deploy from GitHub repo"**
5. Find and select your repository: **`theperiodapp`**
6. Railway will create a new service

### 1.2 Configure Root Directory

1. Click on the newly created service
2. Go to **Settings** tab
3. Scroll to **Root Directory**
4. Set it to: **`backend`**
5. Save changes

### 1.3 Set Environment Variables

1. Go to **Variables** tab in Railway
2. Add each of these variables (click **+ New Variable** for each):

```
SUPABASE_URL=your_supabase_url_here
SUPABASE_KEY=your_supabase_anon_key_here
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
JWT_SECRET_KEY=your_32_character_secret_key_here
JWT_ALGORITHM=HS256
GEMINI_API_KEY=your_gemini_api_key_here
RAPIDAPI_KEY=your_rapidapi_key_here
CORS_ORIGINS=http://localhost:5173
```

**Note**: We'll update `CORS_ORIGINS` later with your Vercel URL.

### 1.4 Get Your Backend URL

1. Railway will automatically deploy after you add variables
2. Wait for deployment to complete (2-3 minutes)
3. Go to **Settings** → **Networking**
4. Click **"Generate Domain"** (or use the provided one)
5. **Copy your Railway URL** (e.g., `https://your-app.up.railway.app`)

**✅ Backend deployed! Save this URL - you'll need it for Step 2.**

---

## 🌐 STEP 2: Deploy Frontend to Vercel

### 2.1 Create Vercel Project

1. Go to **https://vercel.com**
2. Sign in with **GitHub**
3. Click **"Add New"** → **"Project"**
4. Find and select your repository: **`theperiodapp`**
5. Click **"Import"**

### 2.2 Configure Project Settings

In the project configuration:

1. **Framework Preset**: Select **"Vite"** (or leave auto-detected)
2. **Root Directory**: Click **"Edit"** and set to **`frontend`**
3. **Build Command**: `npm run build` (should be auto-filled)
4. **Output Directory**: `dist` (should be auto-filled)
5. **Install Command**: `npm install` (should be auto-filled)

### 2.3 Set Environment Variable

1. Scroll down to **"Environment Variables"**
2. Click **"Add"**
3. Add this variable:
   - **Key**: `VITE_API_BASE_URL`
   - **Value**: Your Railway backend URL from Step 1.4
     - Example: `https://your-app.up.railway.app`
4. Click **"Save"**

### 2.4 Deploy

1. Click **"Deploy"**
2. Wait for build to complete (1-2 minutes)
3. Vercel will show you a deployment URL

**✅ Frontend deployed! Copy your Vercel URL.**

---

## 🔄 STEP 3: Update CORS in Railway

### 3.1 Update CORS_ORIGINS

1. Go back to **Railway dashboard**
2. Select your backend service
3. Go to **Variables** tab
4. Find **`CORS_ORIGINS`**
5. Click **Edit**
6. Update the value to your Vercel URL:
   ```
   https://your-vercel-app.vercel.app
   ```
   (Replace with your actual Vercel URL from Step 2.4)
7. Save

### 3.2 Wait for Redeployment

Railway will automatically redeploy with the new CORS settings (takes ~1-2 minutes).

---

## ✅ STEP 4: Test Your Deployment

### 4.1 Test Frontend

1. Visit your **Vercel URL**
2. Check if the homepage loads
3. Open browser **DevTools** (F12) → **Console** tab
4. Look for any errors

### 4.2 Test Backend

1. Visit: `https://your-railway-url.railway.app/health`
2. Should return: `{"status":"healthy"}`

### 4.3 Test Login/Registration

1. Go to your Vercel URL
2. Try to register a new account
3. Or try to login
4. Check browser console for any CORS errors

---

## 🔧 Troubleshooting

### Backend Not Starting

**Check Railway Logs:**
1. Go to Railway dashboard
2. Select your service
3. Click **"Deployments"** tab
4. Click on the latest deployment
5. Check **"Logs"** for errors

**Common Issues:**
- Missing environment variables
- Wrong Python version
- Import errors

### Frontend Build Fails

**Check Vercel Logs:**
1. Go to Vercel dashboard
2. Select your project
3. Click on failed deployment
4. Check build logs

**Common Issues:**
- Missing `VITE_API_BASE_URL`
- Build errors
- Missing dependencies

### CORS Errors

**Symptoms:** 
- `Access-Control-Allow-Origin` errors in browser console
- Login/API calls failing

**Fix:**
1. Verify `CORS_ORIGINS` in Railway includes your Vercel URL
2. No trailing slashes in URLs
3. Redeploy backend after updating CORS

### "Failed to Fetch" Errors

**Check:**
1. Backend is running (test `/health` endpoint)
2. Backend URL is correct in Vercel env vars
3. No typos in environment variable names

---

## 📝 Environment Variables Quick Reference

### Railway (Backend) Variables:
```env
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJxxx...
SUPABASE_SERVICE_ROLE_KEY=eyJxxx...
JWT_SECRET_KEY=your-32-character-secret-key
JWT_ALGORITHM=HS256
GEMINI_API_KEY=AIza...
RAPIDAPI_KEY=xxx...
CORS_ORIGINS=https://your-app.vercel.app
```

### Vercel (Frontend) Variables:
```env
VITE_API_BASE_URL=https://your-app.railway.app
```

---

## 🎉 You're Done!

Your app is now live:
- **Frontend**: `https://your-app.vercel.app`
- **Backend**: `https://your-app.railway.app`

Both will auto-deploy on every push to `main` branch!

---

## 📞 Need Help?

- Check deployment logs in Railway/Vercel dashboards
- Verify all environment variables are set correctly
- Test backend health endpoint directly
- Check browser console for detailed error messages






