# PeriodCycle.AI - Menstrual Cycle Tracking Application

A comprehensive menstrual cycle tracking application with AI-powered health recommendations, cycle predictions, and personalized wellness guidance.

## Features

- User authentication and profile management
- Menstrual cycle tracking with phase calculation
- Hormone data visualization
- Nutrition and exercise recommendations
- Period logging
- AI chatbot for health queries
- Multilingual support (English, Hindi, Gujarati)
- Beautiful, modern UI with pastel color scheme

## Tech Stack

### Backend
- FastAPI
- Supabase (PostgreSQL)
- JWT Authentication
- Google Gemini API
- Women's Health API Integration

### Frontend
- React 19.1.1
- Vite 7.1.7
- Tailwind CSS 3.4.18
- React Router DOM 7.9.3

## Setup Instructions

### Backend Setup

1. Navigate to backend directory:
```bash
cd backend
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables in `.env`:
```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
GEMINI_API_KEY=your_gemini_api_key
RAPIDAPI_KEY=your_rapidapi_key
JWT_SECRET_KEY=your_jwt_secret_key
JWT_ALGORITHM=HS256
```

4. Run the server:
```bash
uvicorn main:app --reload
```

### Frontend Setup

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Run the development server:
```bash
npm run dev
```

## Database Setup

See `database/schema.sql` for database schema and RLS policies.

## API Documentation

API documentation available at `http://localhost:8000/docs` when backend is running.

