# Environment Variables Setup

## Overview

The application uses `.env` files to store sensitive configuration. These files are **ignored by git** and **not visible to Cursor** for security.

## Files Created

### Backend `.env` file
Location: `backend/.env`

Required variables:
```env
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
GEMINI_API_KEY=your_gemini_api_key
RAPIDAPI_KEY=your_rapidapi_key
JWT_SECRET_KEY=your_jwt_secret_key_minimum_32_characters_long
JWT_ALGORITHM=HS256
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

### Frontend `.env` file
Location: `frontend/.env`

Required variables:
```env
VITE_API_BASE_URL=http://localhost:8000
```

## How to Fill In Your Keys

1. **Open the `.env` files** in your editor:
   - `backend/.env` - Add your backend API keys
   - `frontend/.env` - Update if your backend runs on a different port

2. **Get your API keys:**

   **Supabase:**
   - Go to your Supabase project dashboard
   - Settings → API
   - Copy "Project URL" → `SUPABASE_URL`
   - Copy "anon public" key → `SUPABASE_KEY`

   **Google Gemini:**
   - Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Create an API key
   - Copy to `GEMINI_API_KEY`

   **RapidAPI (Women's Health API):**
   - Sign up at [RapidAPI](https://rapidapi.com/)
   - Subscribe to Women's Health API
   - Copy your API key to `RAPIDAPI_KEY`

   **JWT Secret Key:**
   - Generate a secure random string (minimum 32 characters)
   - You can use: `openssl rand -hex 32`
   - Copy to `JWT_SECRET_KEY`

3. **Save the files** - The application will automatically load them on startup.

## Security Notes

✅ `.env` files are in `.gitignore` - they won't be committed to git  
✅ Cursor cannot see `.env` files - they're protected  
✅ `.env.example` files are templates - safe to commit  

## Verification

After adding your keys, you can verify the backend loads them correctly:

```bash
cd backend
python3 -c "from config import settings; print('Config loaded:', bool(settings.SUPABASE_URL))"
```

If it prints `Config loaded: True`, your environment variables are being read correctly.

## Troubleshooting

**Backend can't find keys:**
- Make sure `.env` file is in the `backend/` directory
- Check that `python-dotenv` is installed: `pip install python-dotenv`
- Verify file has no syntax errors (no spaces around `=`)

**Frontend can't connect:**
- Check `VITE_API_BASE_URL` matches your backend URL
- Restart the Vite dev server after changing `.env`
- Vite only reads env vars prefixed with `VITE_`

