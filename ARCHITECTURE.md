# Period GPT2 - Architecture Overview

## Project Structure

```
PROJECT2/
├── backend/
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py          # Authentication endpoints
│   │   ├── user.py           # User profile endpoints
│   │   ├── periods.py        # Period logging endpoints
│   │   ├── ai_chat.py        # AI chat endpoints
│   │   ├── cycles.py         # Cycle prediction endpoints
│   │   └── wellness.py      # Wellness data endpoints
│   ├── main.py               # FastAPI application entry point
│   ├── config.py             # Configuration settings
│   ├── database.py           # Supabase client
│   ├── auth_utils.py         # JWT and password utilities
│   ├── cycle_utils.py        # Cycle prediction and phase mapping
│   └── requirements.txt      # Python dependencies
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ProtectedRoute.jsx
│   │   │   ├── ErrorBoundary.jsx
│   │   │   ├── SafetyDisclaimer.jsx
│   │   │   ├── LogoutButton.jsx
│   │   │   ├── Navbar.jsx
│   │   │   ├── SimpleAuthComponent.jsx
│   │   │   ├── Calendar.jsx
│   │   │   └── PeriodLogModal.jsx
│   │   ├── pages/
│   │   │   ├── Home.jsx
│   │   │   ├── Login.jsx
│   │   │   ├── Register.jsx
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Profile.jsx
│   │   │   ├── Chat.jsx
│   │   │   ├── Wellness.jsx
│   │   │   └── NotFound.jsx
│   │   ├── utils/
│   │   │   ├── api.js
│   │   │   ├── greetings.js
│   │   │   └── indianDate.js
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── postcss.config.js
│
├── database/
│   └── schema.sql            # Database schema and RLS policies
│
├── README.md
├── SETUP.md
└── .gitignore
```

## Backend Architecture

### FastAPI Application
- **Framework**: FastAPI with async/await support
- **Authentication**: JWT tokens with 7-day expiration
- **Password Hashing**: pbkdf2_sha256 via passlib
- **Database**: Supabase (PostgreSQL) with Row Level Security

### API Endpoints

#### Authentication (`/auth`)
- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `GET /auth/me` - Get current user
- `POST /auth/logout` - Logout (client-side)

#### User Profile (`/user`)
- `GET /user/profile` - Get user profile
- `POST /user/profile` - Update user profile
- `POST /user/change-password` - Change password
- `POST /user/remove-item` - Remove saved item

#### Period Logging (`/periods`)
- `POST /periods/log` - Log period entry
- `GET /periods/logs` - Get all period logs
- `PUT /periods/log/{log_id}` - Update period log
- `DELETE /periods/log/{log_id}` - Delete period log

#### Cycle Predictions (`/cycles`)
- `POST /cycles/predict` - Generate cycle predictions
- `GET /cycles/current-phase` - Get current phase-day
- `GET /cycles/phase-map` - Get phase mappings for date range

#### Wellness Data (`/wellness`)
- `GET /wellness/hormones` - Get hormone data
- `GET /wellness/nutrition` - Get nutrition data
- `GET /wellness/exercises` - Get exercise data

#### AI Chat (`/ai`)
- `POST /ai/chat` - Send chat message
- `GET /ai/chat-history` - Get chat history

### Cycle Prediction Flow

1. User provides past cycle data (cycle start dates and period lengths)
2. Backend calls Women's Health API `/process_cycle_data` to get request_id
3. Backend fetches predictions using request_id
4. Backend generates phase-day mappings (p1-p12, f1-f30, o1-o8, l1-l25)
5. Mappings stored in `user_cycle_days` table
6. Frontend displays calendar with phase colors

## Frontend Architecture

### React Application
- **Framework**: React 19.1.1
- **Build Tool**: Vite 7.1.7
- **Routing**: React Router DOM 7.9.3
- **Styling**: Tailwind CSS 3.4.18

### Component Structure

#### Pages
- **Home** - Landing page
- **Login/Register** - Authentication pages
- **Dashboard** - Main dashboard with calendar and quick actions
- **Profile** - User profile management
- **Chat** - AI chatbot interface
- **Wellness** - Three-tab interface (Hormones, Nutrition, Exercise)

#### Components
- **ProtectedRoute** - Route protection wrapper
- **ErrorBoundary** - Error handling
- **Navbar** - Navigation bar
- **Calendar** - Phase visualization calendar
- **PeriodLogModal** - Period logging modal
- **SafetyDisclaimer** - Medical disclaimer

### State Management
- Local state with React hooks
- localStorage for authentication tokens
- API calls via utility functions

## Database Schema

### Core Tables
- **users** - User accounts and preferences
- **period_logs** - Period tracking entries
- **user_cycle_days** - Phase-day mappings
- **chat_history** - AI chat conversations

### Wellness Tables
- **hormones_data** - Hormone information by phase-day
- **nutrition_en/hi/gu** - Recipes by language
- **wholefoods_en/hi/gu** - Whole foods by language
- **exercises_en/hi/gu** - Exercises by language

### Security
- Row Level Security (RLS) enabled on all user tables
- JWT token authentication
- Password hashing with pbkdf2_sha256

## Integration Points

### Women's Health API
- Used for cycle predictions
- Endpoints:
  - `/process_cycle_data` - Analyze past cycles
  - `/get_data/{request_id}/predicted_cycle_starts` - Get predictions
  - `/get_data/{request_id}/average_period_length` - Get averages
  - `/predict_cycle_phases` - Predict phases

### Google Gemini API
- Used for AI chat responses
- Model: gemini-2.5-flash
- Context includes user cycle phase and preferences

## Phase-Day ID System

- **Period**: p1-p12 (menstrual phase)
- **Follicular**: f1-f30 (pre-ovulation)
- **Ovulation**: o1-o8 (ovulation window)
- **Luteal**: l1-l25 (post-ovulation)

These IDs are used to:
- Display phase colors on calendar
- Fetch phase-specific wellness data
- Provide personalized recommendations

## Color Scheme

- **Menstrual/Period**: Soft pink (#F8BBD9)
- **Follicular**: Light green/teal (#B2DFDB)
- **Ovulation**: Soft yellow (#FFF8E1)
- **Luteal**: Light purple (#E1BEE7)

## Multilingual Support

- Supported languages: English (en), Hindi (hi), Gujarati (gu)
- Separate tables for nutrition, wholefoods, and exercises per language
- User preference stored in `users.language`
- AI chat responses in user's preferred language

## Security Considerations

1. **Authentication**: JWT tokens with expiration
2. **Password Security**: pbkdf2_sha256 hashing
3. **Database Security**: Row Level Security policies
4. **CORS**: Configured for specific origins
5. **Input Validation**: Pydantic models for request validation
6. **Error Handling**: Graceful error responses

## Future Enhancements

1. Real-time cycle predictions
2. Push notifications for cycle reminders
3. Data export functionality
4. Social features (optional)
5. Advanced analytics
6. Integration with health devices
7. More language support

