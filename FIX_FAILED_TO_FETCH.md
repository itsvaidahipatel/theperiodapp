# Fix "Failed to Fetch" Error - Step by Step

## 🎯 Root Cause

Frontend on Vercel cannot reach backend on Railway due to:
1. Wrong API URL (still using localhost)
2. Missing CORS configuration
3. Environment variables not set

---

## ✅ FIX STEP 1: Set Frontend Environment Variable

**In Vercel Dashboard:**

1. Go to **Vercel Dashboard** → Your Project
2. Click **Settings** → **Environment Variables**
3. Add/Update this variable:

   **Key**: `VITE_API_BASE_URL`
   
   **Value**: `https://theperiodapp-production.up.railway.app`
   
   ⚠️ **IMPORTANT**: 
   - Must start with `https://` (NOT `http://`)
   - No trailing slash
   - Use your actual Railway backend URL

4. Click **Save**

5. **Redeploy** frontend (or wait for auto-redeploy)

---

## ✅ FIX STEP 2: Set Backend CORS

**In Railway Dashboard:**

1. Go to **Railway Dashboard** → Your Service
2. Click **Variables** tab
3. Add/Update `CORS_ORIGINS`:

   **Value**: `https://theperiodapp.vercel.app,http://localhost:5173`
   
   ⚠️ **IMPORTANT**:
   - Replace `theperiodapp.vercel.app` with your actual Vercel production URL
   - Separate multiple URLs with commas (NO spaces)
   - Include `http://localhost:5173` for local development

4. Click **Save**

5. Railway will **auto-redeploy** backend

---

## ✅ FIX STEP 3: Verify Backend is Running

Visit this URL in your browser:

```
https://theperiodapp-production.up.railway.app/health
```

**Expected Response:**
```json
{"status":"healthy"}
```

If this doesn't work, check Railway logs for errors.

---

## ✅ FIX STEP 4: Test the Connection

1. Open your **Vercel frontend URL**
2. Open **Browser DevTools** (F12)
3. Go to **Console** tab
4. Try to **login/register**
5. Check for errors:
   - ❌ "Failed to fetch" → Backend not reachable
   - ❌ "CORS error" → CORS not configured correctly
   - ✅ No errors → It's working!

---

## 🔍 Troubleshooting

### Still Getting "Failed to Fetch"?

1. **Check Backend URL:**
   - Open browser DevTools → Network tab
   - Try to login
   - See what URL it's trying to call
   - Should be: `https://theperiodapp-production.up.railway.app/auth/login`

2. **Check Environment Variable:**
   - In Vercel Dashboard → Environment Variables
   - Verify `VITE_API_BASE_URL` is set correctly
   - Make sure it's added for **Production** environment

3. **Check CORS:**
   - In Railway Dashboard → Variables
   - Verify `CORS_ORIGINS` includes your Vercel URL
   - No typos, no spaces between URLs

4. **Check Backend Logs:**
   - Railway Dashboard → Deployments → Latest → Logs
   - Look for CORS errors or connection issues

---

## 📝 Quick Checklist

- [ ] `VITE_API_BASE_URL` set in Vercel (with https://)
- [ ] `CORS_ORIGINS` set in Railway (with your Vercel URL)
- [ ] Backend health endpoint works (`/health`)
- [ ] Frontend redeployed after env var change
- [ ] Backend redeployed after CORS change
- [ ] Browser console shows no CORS errors

---

## 🎉 Once Fixed

Your app will work:
- ✅ Frontend can call backend API
- ✅ Login/Registration works
- ✅ All API endpoints accessible
- ✅ No CORS errors




