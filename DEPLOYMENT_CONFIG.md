# Deployment Configuration Guide

This guide explains how to configure Vercel and Railway for branch-based deployments with automatic staging and production environments.

---

## Vercel Configuration

### Overview

Vercel automatically handles branch-based deployments:
- **`main` branch** → Production deployment (your main domain)
- **`develop` branch** (and other branches) → Preview deployments (unique URLs)

### Setup Steps

#### 1. Connect Repository to Vercel

1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Click **Add New Project**
3. Import your GitHub repository
4. Configure the project:
   - **Framework Preset**: Vite
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`

#### 2. Configure Environment Variables

1. Go to **Settings** → **Environment Variables**
2. Add the following variables:

   **Production Environment:**
   ```
   VITE_API_BASE_URL=https://your-railway-production-url.railway.app
   ```

   **Preview Environment:**
   ```
   VITE_API_BASE_URL=https://your-railway-staging-url.railway.app
   ```
   (Or use the same as production if you only have one Railway service)

   **Development Environment:**
   ```
   VITE_API_BASE_URL=http://localhost:8000
   ```

3. Make sure to select all three environments (Production, Preview, Development)

#### 3. Configure Branch Deployments

By default, Vercel will:
- Deploy `main` branch to production
- Deploy all other branches (including `develop`) as previews

You can customize this in **Settings** → **Git**:
- **Production Branch**: `main`
- **Preview Branches**: All branches (default)

#### 4. Optional: Custom Domain for Production

1. Go to **Settings** → **Domains**
2. Add your custom domain
3. Follow DNS configuration instructions

### Vercel Configuration File

The `frontend/vercel.json` file is already configured correctly:

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite",
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ]
}
```

This ensures:
- Single Page Application routing works correctly
- Build output goes to the `dist` directory
- Vite framework is properly configured

---

## Railway Configuration

### Overview

Railway can handle branch-based deployments in two ways:

**Option 1: Single Service with Branch Deployments** (Recommended for simplicity)
- One Railway service
- Deploy from `main` branch to production
- `develop` branch can also deploy to the same service (or separate)

**Option 2: Separate Services for Staging and Production** (Recommended for isolation)
- Create two Railway services
- Production service deploys from `main`
- Staging service deploys from `develop`

### Setup Steps - Option 1 (Single Service)

#### 1. Connect Repository to Railway

1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Click **New Project**
3. Select **Deploy from GitHub repo**
4. Choose your repository

#### 2. Configure the Service

1. Railway will auto-detect it's a Python project
2. Configure the service:
   - **Root Directory**: `backend`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Railway will automatically detect Python and install dependencies

#### 3. Set Environment Variables

1. Go to the service → **Variables** tab
2. Add all required environment variables (same as `backend/.env`):

```
SUPABASE_URL=your-supabase-url
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
GEMINI_API_KEY=your-gemini-api-key
RAPIDAPI_KEY=your-rapidapi-key
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
CORS_ORIGINS=https://your-vercel-production-url.vercel.app,https://your-vercel-preview-url.vercel.app
```

**Important**: Add your Vercel production and preview URLs to `CORS_ORIGINS`

#### 4. Configure Branch Deployment

1. Go to service → **Settings** → **Source**
2. Set **Production Branch**: `main`
3. Railway will automatically deploy from `main` branch

**For develop branch deployments**, you can:
- Manually deploy from `develop` branch when needed
- Or create a separate service (Option 2)

### Setup Steps - Option 2 (Separate Services)

#### 1. Create Production Service

1. Create a new Railway project or use existing
2. Add a new service from GitHub repo
3. Configure as above but set **Production Branch** to `main`
4. Name it "Backend Production" or similar

#### 2. Create Staging Service

1. In the same Railway project, add another service
2. Connect to the same GitHub repository
3. Set **Production Branch** to `develop`
4. Name it "Backend Staging" or similar

#### 3. Set Environment Variables

Set environment variables for both services:
- **Production Service**: Use production database/API keys
- **Staging Service**: Can use the same or separate staging resources

#### 4. Configure CORS

**Production Service:**
```
CORS_ORIGINS=https://your-production-vercel-url.vercel.app
```

**Staging Service:**
```
CORS_ORIGINS=https://your-preview-vercel-url.vercel.app,http://localhost:5173
```

### Railway Configuration File

The `railway.json` file in the root is already configured:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "cd backend && uvicorn main:app --host=0.0.0.0 --port=${PORT}",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

This ensures:
- Python backend is built correctly
- Server starts on the correct port
- Automatic restart on failures

---

## Deployment Workflow

### Development → Staging

1. **Work on `develop` branch locally**
   ```bash
   git checkout develop
   ./start.sh  # Test locally
   ```

2. **Push to GitHub**
   ```bash
   git add .
   git commit -m "Your changes"
   git push origin develop
   ```

3. **Automatic Deployments**:
   - Vercel: Creates a preview deployment (unique URL)
   - Railway: If configured, deploys staging service

4. **Test in Staging**:
   - Use the Vercel preview URL
   - Verify all features work

### Staging → Production

1. **Merge develop into main**
   ```bash
   git checkout main
   git pull origin main
   git merge develop
   git push origin main
   ```

2. **Automatic Deployments**:
   - Vercel: Deploys to production domain
   - Railway: Deploys production service from `main` branch

3. **Monitor**:
   - Check Vercel deployment logs
   - Check Railway deployment logs
   - Test production site

---

## Environment Variables Summary

### Frontend (Vercel)

| Environment | Variable | Value |
|------------|----------|-------|
| Production | `VITE_API_BASE_URL` | `https://your-railway-prod.railway.app` |
| Preview | `VITE_API_BASE_URL` | `https://your-railway-staging.railway.app` |
| Development | `VITE_API_BASE_URL` | `http://localhost:8000` |

### Backend (Railway)

| Variable | Production | Staging |
|----------|-----------|---------|
| `SUPABASE_URL` | Production DB | Staging DB (or same) |
| `SUPABASE_KEY` | Production Key | Staging Key (or same) |
| `CORS_ORIGINS` | Production Vercel URL | Preview Vercel URLs + localhost |

---

## Troubleshooting

### Vercel Deployment Issues

**Issue**: Build fails
- Check build logs in Vercel dashboard
- Ensure `frontend/vercel.json` is correct
- Verify `package.json` has correct build scripts

**Issue**: Preview URLs not working
- Check that `develop` branch is pushed to GitHub
- Verify Vercel is connected to the correct repository
- Check branch deployment settings

### Railway Deployment Issues

**Issue**: Service won't start
- Check Railway logs
- Verify `railway.json` is in the root directory
- Ensure environment variables are set correctly
- Check that `PORT` environment variable is available (Railway sets this automatically)

**Issue**: CORS errors
- Verify `CORS_ORIGINS` includes your Vercel URLs
- Check that frontend `VITE_API_BASE_URL` matches Railway service URL
- Ensure CORS regex in `backend/main.py` allows Vercel preview domains

**Issue**: Database connection errors
- Verify Supabase environment variables are correct
- Check Supabase project is active
- Verify network access is allowed

---

## Quick Reference

### Vercel URLs
- Production: `https://your-app.vercel.app`
- Preview: `https://your-app-git-develop-username.vercel.app`

### Railway URLs
- Production: `https://your-service.up.railway.app`
- Staging: `https://your-staging-service.up.railway.app`

### Commands
```bash
# Deploy to staging
git checkout develop
git push origin develop

# Deploy to production
git checkout main
git merge develop
git push origin main
```

---

## Next Steps

After configuring deployments:

1. Test the workflow:
   - Push to `develop` → Verify staging deployment
   - Merge to `main` → Verify production deployment

2. Set up monitoring:
   - Add error tracking (e.g., Sentry)
   - Set up deployment notifications
   - Monitor Railway and Vercel logs

3. Configure custom domains (optional):
   - Add custom domain to Vercel
   - Add custom domain to Railway (if needed)

Happy deploying! 🚀
