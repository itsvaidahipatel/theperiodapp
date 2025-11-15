# Period GPT2 - Setup Guide

## Prerequisites

- Python 3.8+
- Node.js 18+
- Supabase account
- Google Gemini API key
- RapidAPI key for Women's Health API

## Backend Setup

1. **Navigate to backend directory:**
```bash
cd backend
```

2. **Create virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables:**
Create a `.env` file in the `backend` directory:
```env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
GEMINI_API_KEY=your_gemini_api_key
RAPIDAPI_KEY=your_rapidapi_key
JWT_SECRET_KEY=your_jwt_secret_key
JWT_ALGORITHM=HS256
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

5. **Set up database:**
- Go to your Supabase project
- Navigate to SQL Editor
- Run the SQL from `database/schema.sql`

6. **Run the server:**
```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`
API documentation at `http://localhost:8000/docs`

## Frontend Setup

1. **Navigate to frontend directory:**
```bash
cd frontend
```

2. **Install dependencies:**
```bash
npm install
```

3. **Set up environment variables (optional):**
Create a `.env` file in the `frontend` directory:
```env
VITE_API_BASE_URL=http://localhost:8000
```

4. **Run the development server:**
```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`

## Database Setup

1. **Create tables:**
   - Run the SQL from `database/schema.sql` in your Supabase SQL Editor

2. **Set up Row Level Security (RLS):**
   - The schema includes RLS policies
   - For development, you may need to adjust policies or use service_role key
   - For production, ensure proper RLS policies are in place

3. **Seed data (optional):**
   - You'll need to populate `hormones_data`, `nutrition_*`, `wholefoods_*`, and `exercises_*` tables
   - These can be populated with sample data based on phase_day_id

## API Keys Setup

### Google Gemini API
1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create an API key
3. Add it to your `.env` file as `GEMINI_API_KEY`

### RapidAPI - Women's Health API
1. Sign up at [RapidAPI](https://rapidapi.com/)
2. Subscribe to the Women's Health API
3. Get your API key
4. Add it to your `.env` file as `RAPIDAPI_KEY`

### Supabase
1. Create a project at [Supabase](https://supabase.com/)
2. Get your project URL and anon key from Settings > API
3. Add them to your `.env` file

## Testing the Application

1. **Start backend:**
```bash
cd backend
uvicorn main:app --reload
```

2. **Start frontend:**
```bash
cd frontend
npm run dev
```

3. **Register a new user:**
   - Go to `http://localhost:5173/register`
   - Create an account

4. **Generate cycle predictions:**
   - After logging in, you'll need to call the `/cycles/predict` endpoint with past cycle data
   - This can be done through the API docs or by implementing a UI for it

## Troubleshooting

### CORS Errors
- Ensure `CORS_ORIGINS` in `.env` includes your frontend URL
- Check that credentials are allowed in CORS middleware

### Database Connection Issues
- Verify Supabase URL and key are correct
- Check RLS policies if queries fail
- Ensure tables are created

### API Key Issues
- Verify all API keys are set correctly in `.env`
- Check API key permissions and quotas

### Phase Calculation Not Working
- Ensure you have past cycle data
- Call `/cycles/predict` endpoint with valid data
- Check that `user_cycle_days` table is being populated

## Next Steps

1. Populate wellness data tables (hormones, nutrition, exercises)
2. Add more cycle prediction logic
3. Implement additional features as needed
4. Deploy to production

