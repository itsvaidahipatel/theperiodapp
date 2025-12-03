# Vercel Setup - Quick Reference

## ⚠️ IMPORTANT: Set Root Directory in Dashboard

Vercel cannot read `rootDirectory` from `vercel.json` anymore. You **MUST** set it in the dashboard:

### Steps:

1. Go to **Vercel Dashboard**: https://vercel.com
2. Select your project: **theperiodapp**
3. Go to **Settings** → **General** tab
4. Scroll to **Root Directory** section
5. Set the value to: **`frontend`**
6. Click **Save**

### What this does:

- Tells Vercel your React/Vite app is in the `frontend/` folder
- Vercel will automatically find `package.json` there
- Vercel will auto-detect Vite and build correctly

---

## ✅ Current Configuration

**vercel.json**: `{}` (empty - Vercel auto-detects everything)

**Root Directory**: Set in dashboard → `frontend`

**Build**: Vercel automatically detects:
- Framework: Vite
- Build Command: `npm run build` (auto-detected)
- Output Directory: `dist` (auto-detected)

---

## 🔄 After Setting Root Directory

1. Vercel will automatically redeploy
2. Build should succeed
3. Frontend will be live at your Vercel URL

---

## 📝 Environment Variables

Don't forget to set in Vercel Dashboard → Settings → Environment Variables:

- **Key**: `VITE_API_BASE_URL`
- **Value**: Your Railway backend URL (e.g., `https://your-app.up.railway.app`)

