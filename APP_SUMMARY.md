# PeriodCycle.AI - Complete Application Summary

## 📱 Application Overview

**PeriodCycle.AI** is a comprehensive, AI-powered menstrual cycle tracking application that provides personalized health insights, cycle predictions, and wellness recommendations. The app combines advanced machine learning algorithms with user-friendly design to help users understand and manage their menstrual health.

---

## 🏗️ Architecture

### System Architecture Pattern
- **Frontend-Backend Separation**: React SPA + RESTful API
- **Database**: PostgreSQL (via Supabase) with Row Level Security
- **External APIs**: RapidAPI (cycle predictions), Google Gemini (AI chat)
- **Deployment**: Vercel (frontend) + Railway (backend)

### Technology Stack

#### Backend
- **Framework**: FastAPI 0.115.0 (Python 3.13)
- **Database**: Supabase (PostgreSQL)
- **Authentication**: JWT tokens (7-day expiration)
- **Password Security**: pbkdf2_sha256 hashing
- **API Integration**: 
  - RapidAPI (Women's Health API)
  - Google Gemini 2.5 Flash (AI chat)

#### Frontend
- **Framework**: React 19.1.1
- **Build Tool**: Vite 7.1.7
- **Routing**: React Router DOM 7.9.3
- **Styling**: Tailwind CSS 3.4.18
- **Charts**: Recharts 3.4.1
- **Calendar**: React Calendar 5.1.0

---

## 🎯 Core Features

### 1. **User Authentication & Profile Management**
- Secure registration/login with JWT tokens
- User profile with preferences (language, cuisine, exercise, allergies)
- Password change functionality
- Multi-language support (English, Hindi, Gujarati)

### 2. **Adaptive Cycle Prediction System** ⭐
The most sophisticated feature - uses **probabilistic, data-driven algorithms**:

#### Key Concepts:
- **No Fixed Values**: All phase lengths adapt to user data
- **Bayesian Learning**: System improves with each logged period
- **Fertility Probabilities**: Each day has a fertility score (0.0-1.0)
- **Uncertainty Tracking**: Standard deviations indicate prediction confidence

#### How It Works:
1. **Initial State**: Uses population priors (luteal: 14±2 days, period: 5 days)
2. **Learning Phase**: As user logs periods, system calculates:
   - Observed luteal length: `period_start - predicted_ovulation`
   - Updates estimates using Bayesian smoothing: `(old × 0.6) + (observed × 0.4)`
3. **Prediction**: 
   - Ovulation date: `cycle_start + (cycle_length - luteal_mean)`
   - Fertility probability: Combines normal distribution (60%) + sperm survival (40%)
   - Phase assignment based on fertility thresholds

#### Data Sources (Priority Order):
1. **RapidAPI** (confidence: 0.9) - Primary source when available
2. **Adjusted** (confidence: 0.7) - RapidAPI predictions with manual phase calculation
3. **Fallback** (confidence: 0.4) - Local calculation using user data

### 3. **Period Logging & Tracking**
- Log period start/end dates
- Automatic cycle length calculation
- Luteal phase estimation updates
- Historical period data visualization

### 4. **Phase-Day ID System**
Unique identifier system for each day:
- **Period**: `p1` - `p12` (menstrual phase)
- **Follicular**: `f1` - `f30` (pre-ovulation)
- **Ovulation**: `o1` - `o8` (ovulation window)
- **Luteal**: `l1` - `l25` (post-ovulation)

Used for:
- Calendar visualization with color coding
- Phase-specific wellness data retrieval
- Personalized recommendations

### 5. **Wellness Recommendations**
Three categories of phase-specific content:

#### Hormones
- Daily hormone levels (Estrogen, Progesterone, FSH, LH)
- Visual charts showing hormone fluctuations
- Phase-specific hormone information

#### Nutrition
- Phase-specific recipes
- Whole foods recommendations
- Cuisine preferences (North Indian, South Indian, etc.)
- Multilingual content (English, Hindi, Gujarati)

#### Exercise
- Phase-appropriate workout recommendations
- Exercise intensity guidance
- Recovery suggestions

### 6. **AI-Powered Health Chatbot**
- **Model**: Google Gemini 2.5 Flash
- **Context-Aware**: Includes user's current cycle phase
- **Multilingual**: Responds in user's preferred language
- **Medical Safety**: Only provides evidence-based information
- **Personalization**: Uses user name, preferences, and cycle data

### 7. **Interactive Calendar**
- Visual phase representation with color coding
- Click to view daily details
- Period logging directly from calendar
- Fertility probability indicators

### 8. **Dashboard**
- Current phase display
- Quick actions (log period, view calendar)
- Recent activity
- Personalized greetings

---

## 🔬 Key Algorithms & Concepts

### 1. **Bayesian Luteal Phase Estimation**

```python
# Prior: mean=14 days, sd=2 days
# User observations: weighted 40%
luteal_mean = 0.6 × prior_mean + 0.4 × user_mean
# Clamped to range: 10-18 days
```

**Purpose**: Adapts to individual user's luteal phase length
**Updates**: When user logs period, calculates observed luteal and updates estimate

### 2. **Ovulation Prediction**

```python
ovulation_date = cycle_start + (cycle_length - luteal_mean)
ovulation_sd = sqrt(cycle_start_sd² + luteal_sd²)
```

**Purpose**: Predicts ovulation date with uncertainty quantification
**Dynamic**: Changes based on user's cycle length and luteal estimate

### 3. **Fertility Probability Calculation**

```python
# Combines two models:
# 60%: Normal distribution (ovulation probability)
# 40%: Sperm survival kernel (5 days before ovulation)
fertility_prob = 0.6 × normal_pdf(offset, ovulation_sd) + 
                 0.4 × sperm_survival(offset)
```

**Purpose**: Provides fertility probability (0.0-1.0) for each day
**Usage**: Determines ovulation phase and fertile window

### 4. **Phase Assignment Rules**

1. **Period**: Days within estimated period length
2. **Ovulation**: `fertility_prob >= 0.6` (high fertility)
3. **Fertile Window**: `fertility_prob >= 0.2` (moderate fertility)
4. **Follicular**: Before ovulation window
5. **Luteal**: After ovulation window, before next cycle

### 5. **Cycle Length Update (Bayesian)**

```python
# When user logs period:
updated_cycle_length = 0.7 × old_cycle_length + 0.3 × new_cycle_length
```

**Purpose**: Smoothly adapts to user's actual cycle patterns

---

## 🔄 Data Flow

### Cycle Prediction Flow

```
1. User Request → GET /cycles/phase-map?start_date=X&end_date=Y
   ↓
2. Check Database → Query user_cycle_days table
   ↓ (if no data)
3. Get User Data → last_period_date, cycle_length
   ↓
4. Try RapidAPI:
   ├─ POST /process_cycle_data (12 cycles)
   ├─ GET /predicted_cycle_starts
   ├─ GET /average_cycle_length
   ├─ GET /average_period_length
   └─ GET /cycle_phases (PRIMARY)
   ↓
5. Generate Phase Mappings:
   ├─ Add fertility probabilities
   ├─ Calculate phase_day_id
   └─ Store in database
   ↓
6. Return phase_map to frontend
```

### Period Logging Flow

```
1. User Logs Period → POST /periods/log
   ↓
2. Calculate Observed Luteal:
   observed_luteal = period_start - predicted_ovulation
   ↓
3. Validate (10-18 days range)
   ↓
4. Update Estimates:
   ├─ Cycle length: Bayesian update
   └─ Luteal mean: Bayesian update
   ↓
5. Regenerate Predictions:
   └─ Trigger cycle prediction update
   ↓
6. Store Period Log
```

### AI Chat Flow

```
1. User Message → POST /ai/chat
   ↓
2. Get User Context:
   ├─ Current phase
   ├─ Cycle length
   ├─ Preferences
   └─ Language
   ↓
3. Build Prompt:
   ├─ Medical safety rules
   ├─ User context
   └─ Language instruction
   ↓
4. Call Gemini API → Get response
   ↓
5. Save Chat History
   ↓
6. Return Response
```

---

## 🗄️ Database Schema

### Core Tables

#### `users`
- User accounts and preferences
- Stores: name, email, password_hash, cycle_length, language, cuisine, exercise, allergies
- **New Fields**: luteal_observations (JSON), luteal_mean, luteal_sd

#### `period_logs`
- Historical period data
- Stores: user_id, start_date, end_date, created_at

#### `user_cycle_days`
- Phase-day mappings for each user
- Stores: user_id, date, phase, phase_day_id, fertility_prob, predicted_ovulation_date, source, confidence

#### `chat_history`
- AI chat conversations
- Stores: user_id, message, role (user/assistant), created_at

### Wellness Tables

#### `hormones_data`
- Hormone information by phase_day_id
- Stores: id (phase_day_id), estrogen, progesterone, fsh, lh levels

#### `nutrition_*` / `wholefoods_*` / `exercises_*`
- Phase-specific content by language
- Tables: `nutrition_en`, `nutrition_hi`, `nutrition_gu`, etc.
- Stores: hormone_id (phase_day_id), content, recipes, etc.

### Security
- **Row Level Security (RLS)**: All user tables protected
- **JWT Authentication**: Token-based access control
- **Password Hashing**: pbkdf2_sha256

---

## 🔌 Integration Points

### 1. **RapidAPI (Women's Health API)**
- **Purpose**: Cycle predictions and phase timeline
- **Endpoints Used**:
  - `POST /process_cycle_data` - Submit past cycles, get request_id
  - `GET /get_data/{request_id}/predicted_cycle_starts` - Future cycle predictions
  - `GET /get_data/{request_id}/average_cycle_length` - Average cycle length
  - `GET /get_data/{request_id}/average_period_length` - Average period length
  - `GET /get_data/{request_id}/cycle_phases` - Complete phase timeline ⭐

- **Requirements**: Minimum 6 cycles (we send 12)
- **Fallback**: Local calculation if API unavailable

### 2. **Google Gemini API**
- **Model**: gemini-2.5-flash (with fallback to other models)
- **Purpose**: AI health chatbot
- **Features**:
  - Context-aware responses
  - Multilingual support
  - Medical safety guardrails
  - Personalized with user data

### 3. **Supabase**
- **Database**: PostgreSQL
- **Authentication**: Row Level Security
- **Real-time**: Potential for real-time features
- **Storage**: Can be extended for file storage

---

## 🎨 UI/UX Features

### Color Scheme (Phase-Based)
- **Period**: Soft pink (#F8BBD9)
- **Follicular**: Light green/teal (#B2DFDB)
- **Ovulation**: Soft yellow (#FFF8E1)
- **Luteal**: Light purple (#E1BEE7)

### Design Principles
- **Pastel Colors**: Soft, calming palette
- **Responsive Design**: Mobile-first approach
- **Accessibility**: Clear typography, good contrast
- **Multilingual UI**: Full translation support

---

## 🔒 Security Features

1. **Authentication**:
   - JWT tokens with 7-day expiration
   - Secure password hashing (pbkdf2_sha256)
   - Token refresh mechanism

2. **Database Security**:
   - Row Level Security (RLS) on all tables
   - User can only access their own data
   - Service role key for admin operations

3. **API Security**:
   - CORS configuration
   - Input validation (Pydantic models)
   - Error handling without exposing internals

4. **Medical Safety**:
   - AI chatbot only provides evidence-based info
   - Clear disclaimers
   - Recommendations to consult healthcare professionals

---

## 📊 Performance Optimizations

1. **Database-First Strategy**:
   - Check database before generating predictions
   - Cache phase mappings
   - Only regenerate when needed

2. **Connection Pooling**:
   - Retry logic with exponential backoff
   - Async database operations
   - Connection error handling

3. **Frontend Optimizations**:
   - Lazy loading
   - Memoization
   - Bundle size reduction (28% smaller)

4. **API Timeouts**:
   - RapidAPI: 10s connect, 30s read
   - Graceful fallbacks

---

## 🚀 Deployment

### Frontend (Vercel)
- **Build**: `npm run build`
- **Output**: `dist/` directory
- **Environment**: `VITE_API_BASE_URL`

### Backend (Railway)
- **Runtime**: Python 3.13
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Environment Variables**: All API keys and database credentials

---

## 📈 Key Metrics & Capabilities

- **Cycle Prediction Accuracy**: Improves with each logged period
- **Fertility Probability**: Calculated for every day
- **Phase Confidence**: 0.4 (fallback) to 0.9 (RapidAPI)
- **Supported Languages**: 3 (English, Hindi, Gujarati)
- **API Endpoints**: 15+ RESTful endpoints
- **Database Tables**: 15+ tables with RLS
- **Response Time**: < 500ms for cached data

---

## 🔮 Future Enhancements

1. **Real-time Updates**: WebSocket support for live predictions
2. **Push Notifications**: Cycle reminders and phase changes
3. **Data Export**: Export cycle data as CSV/PDF
4. **Advanced Analytics**: Cycle pattern analysis, trends
5. **Health Device Integration**: Sync with wearables
6. **Social Features**: Optional community features
7. **More Languages**: Expand multilingual support
8. **Mobile Apps**: Native iOS/Android apps

---

## 🎓 Important Concepts Summary

1. **Adaptive Learning**: System learns from user data using Bayesian methods
2. **Probabilistic Predictions**: Fertility probabilities, not binary yes/no
3. **Uncertainty Quantification**: Standard deviations indicate confidence
4. **Multi-Source Data**: RapidAPI → Adjusted → Fallback hierarchy
5. **Phase-Day System**: Unique IDs for each day enable phase-specific content
6. **Context-Aware AI**: Chatbot uses cycle phase and user preferences
7. **Security First**: RLS, JWT, password hashing, medical safety
8. **Performance**: Database-first caching, connection pooling, retry logic

---

## 📝 Code Organization

### Backend Structure
```
backend/
├── routes/          # API endpoints (auth, cycles, wellness, etc.)
├── cycle_utils.py   # Core prediction algorithms
├── database.py      # Supabase client with retry logic
├── auth_utils.py    # JWT and password utilities
├── config.py        # Environment configuration
└── main.py          # FastAPI app entry point
```

### Frontend Structure
```
frontend/src/
├── pages/          # Route components (Dashboard, Chat, etc.)
├── components/      # Reusable UI components
├── context/        # React context for state
├── utils/          # Helper functions (API, translations, etc.)
└── App.jsx         # Main app component with routing
```

---

This application represents a sophisticated blend of **medical science**, **machine learning**, and **user experience design** to provide accurate, personalized menstrual health tracking and guidance.





