# CORS Configuration Fix

## ✅ Backend CORS is Now Configured

The backend now supports:
- Your specific Vercel domain (from `CORS_ORIGINS` env var)
- All Vercel preview deployments (via regex pattern)

## 🔧 What You Need to Do

### Step 1: Update Railway Environment Variables

In Railway Dashboard → Your Service → Variables:

**Add/Update `CORS_ORIGINS`:**

```
https://theperiodapp.vercel.app,http://localhost:5173
```

**Important:** Replace `theperiodapp.vercel.app` with your actual Vercel production URL.

### Step 2: Update Vercel Environment Variables

In Vercel Dashboard → Your Project → Settings → Environment Variables:

**Add/Update `VITE_API_BASE_URL`:**

```
https://theperiodapp-production.up.railway.app
```

**Important:** Make sure:
- ✅ URL starts with `https://` (not `http://`)
- ✅ No trailing slash
- ✅ Exact URL from Railway dashboard

## ✅ After These Changes

1. Railway will auto-redeploy backend with new CORS settings
2. Vercel will auto-redeploy frontend with correct API URL
3. Login/API calls should work without "Failed to fetch" errors

## 🔍 Verify Backend is Running

Visit: `https://theperiodapp-production.up.railway.app/health`

Should return: `{"status":"healthy"}`

If this doesn't work, check Railway logs for errors.





