# Fix Authentication Errors (403/500)

## 🔍 Error Analysis

### 403 Errors - "Not authenticated"
- **Cause**: Invalid or expired JWT token
- **Fix**: Frontend now automatically clears invalid tokens and redirects to login

### 500 Error on `/auth/login`
- **Cause**: Likely missing `JWT_SECRET_KEY` in Railway environment variables
- **Fix**: Set `JWT_SECRET_KEY` in Railway dashboard

---

## ✅ FIX STEP 1: Set JWT_SECRET_KEY in Railway

**In Railway Dashboard:**

1. Go to **Railway Dashboard** → Your Service
2. Click **Variables** tab
3. Add/Update `JWT_SECRET_KEY`:

   **Key**: `JWT_SECRET_KEY`
   
   **Value**: Generate a secure random string (minimum 32 characters)
   
   **How to generate:**
   ```bash
   openssl rand -hex 32
   ```
   
   Or use an online generator: https://generate-secret.vercel.app/32

4. Click **Save**

5. Railway will **auto-redeploy** backend

---

## ✅ FIX STEP 2: Verify All Required Environment Variables

**In Railway Dashboard → Variables, ensure you have:**

```env
# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJxxx...
SUPABASE_SERVICE_ROLE_KEY=eyJxxx...

# JWT (REQUIRED!)
JWT_SECRET_KEY=your-32-character-secret-key-here
JWT_ALGORITHM=HS256

# API Keys
GEMINI_API_KEY=AIza...
RAPIDAPI_KEY=xxx...

# CORS
CORS_ORIGINS=https://theperiodapp.vercel.app,http://localhost:5173
```

---

## ✅ FIX STEP 3: Test the Fix

1. **Clear browser storage:**
   - Open DevTools (F12)
   - Application tab → Local Storage
   - Clear all items

2. **Try to login:**
   - Go to your Vercel frontend URL
   - Try to login with existing credentials
   - Should work without 500 error

3. **Check Railway logs:**
   - Railway Dashboard → Deployments → Latest → Logs
   - Look for any errors related to JWT or database

---

## 🔍 Troubleshooting

### Still Getting 500 on Login?

1. **Check Railway Logs:**
   - Railway Dashboard → Deployments → Latest → Logs
   - Look for specific error messages
   - Common issues:
     - "JWT_SECRET_KEY not set"
     - Database connection errors
     - Supabase authentication errors

2. **Verify JWT_SECRET_KEY:**
   - In Railway → Variables
   - Make sure `JWT_SECRET_KEY` is set
   - Should be at least 32 characters
   - No spaces or special characters that might break

3. **Test Backend Health:**
   - Visit: `https://theperiodapp-production.up.railway.app/health`
   - Should return: `{"status":"healthy"}`
   - If this fails, backend isn't running properly

### Still Getting 403 Errors?

1. **Clear browser storage:**
   - The frontend now auto-clears invalid tokens
   - But if you have old cached tokens, clear manually:
   - DevTools → Application → Local Storage → Clear

2. **Check token in browser:**
   - DevTools → Application → Local Storage
   - Look for `access_token`
   - If it exists but you get 403, token is invalid
   - Frontend will auto-clear it on next 403 response

3. **Verify JWT_SECRET_KEY matches:**
   - If you changed `JWT_SECRET_KEY` in Railway, all existing tokens are invalid
   - Users need to login again to get new tokens

---

## 📝 What Was Fixed

1. **Frontend (`api.js`):**
   - Now automatically clears invalid tokens on 401/403 errors
   - Redirects to login page when authentication fails
   - Better error handling

2. **Backend (`config.py`):**
   - Improved JWT_SECRET_KEY loading from environment
   - Better error messages for configuration issues

3. **Backend (`auth.py`):**
   - More specific error messages for login failures
   - Better debugging information

---

## 🎉 After Fixing

- ✅ Login should work without 500 errors
- ✅ Invalid tokens are automatically cleared
- ✅ Users are redirected to login when tokens expire
- ✅ Better error messages for debugging

