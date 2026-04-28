-- PeriodCycle.AI — definitive database blueprint
-- Aligns with FastAPI (stateless calendar + optional user_cycle_days cache) and Supabase.
-- period_events is intentionally omitted (deprecated). user_cycle_days is an optional cache only.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------------
-- users
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    last_period_date DATE,
    cycle_length INTEGER DEFAULT 28,
    avg_bleeding_days INTEGER DEFAULT 5,
    language VARCHAR(10) DEFAULT 'en',
    favorite_cuisine VARCHAR(100),
    favorite_exercise VARCHAR(100),
    interests JSONB DEFAULT '[]'::jsonb,
    saved_items JSONB DEFAULT '{}'::jsonb,
    -- Luteal learning (stored payload matches cycle_utils JSON encode/decode)
    luteal_observations TEXT DEFAULT '[]',
    luteal_mean DOUBLE PRECISION,
    luteal_sd DOUBLE PRECISION,
    -- Notifications
    push_notifications_enabled BOOLEAN DEFAULT TRUE,
    fcm_token TEXT,
    notification_preferences JSONB DEFAULT '{}'::jsonb,
    last_notification_sent_date DATE,
    last_anomaly_notification_cycle_start DATE,
    -- Late-period anchor shift (stateless calendar)
    late_period_anchor_shift_days INTEGER NOT NULL DEFAULT 0,
    late_period_last_shift_at TIMESTAMPTZ,
    -- RapidAPI cache (optional)
    rapidapi_request_id VARCHAR(255),
    rapidapi_request_id_expires_at TIMESTAMPTZ,
    consent_accepted BOOLEAN NOT NULL DEFAULT FALSE,
    consent_timestamp TIMESTAMPTZ,
    privacy_policy_version TEXT,
    consent_language TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- period_logs (one row per bleeding start date; end_date + is_manual_end from live API)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS period_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    end_date DATE,
    is_manual_end BOOLEAN NOT NULL DEFAULT FALSE,
    flow VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, date)
);

-- ---------------------------------------------------------------------------
-- period_start_logs — derived cycle anchors + immutable completed-cycle JSON
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS period_start_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    start_date DATE NOT NULL,
    is_confirmed BOOLEAN NOT NULL DEFAULT TRUE,
    is_outlier BOOLEAN NOT NULL DEFAULT FALSE,
    cycle_data_json JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, start_date)
);

CREATE OR REPLACE FUNCTION update_period_start_logs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS period_start_logs_updated_at ON period_start_logs;
CREATE TRIGGER period_start_logs_updated_at
    BEFORE UPDATE ON period_start_logs
    FOR EACH ROW
    EXECUTE FUNCTION update_period_start_logs_updated_at();

COMMENT ON COLUMN period_start_logs.cycle_data_json IS
    'Immutable phase rows for the completed cycle ending before the next start. Not overwritten once set.';

-- ---------------------------------------------------------------------------
-- user_cycle_days — OPTIONAL cache of precomputed phases (safe to truncate; app is stateless)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_cycle_days (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    phase VARCHAR(50) NOT NULL,
    phase_day_id VARCHAR(10) NOT NULL,
    prediction_confidence DOUBLE PRECISION,
    ovulation_offset INTEGER,
    is_predicted BOOLEAN DEFAULT TRUE,
    rapidapi_request_id VARCHAR(255),
    PRIMARY KEY (user_id, date)
);

COMMENT ON TABLE user_cycle_days IS
    'Optional denormalized cache. Phases can always be recomputed from period_logs + users; rows may be deleted any time.';

-- ---------------------------------------------------------------------------
-- chat_history
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    response TEXT NOT NULL,
    language VARCHAR(10) DEFAULT 'en',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- feedback
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_name VARCHAR(255),
    user_email VARCHAR(255),
    subject VARCHAR(500) NOT NULL,
    message TEXT NOT NULL,
    type VARCHAR(50) DEFAULT 'general',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- hormones_data_v2 — reference rows keyed by phase_day_id string (e.g. p1, f5, l10)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.hormones_data_v2 (
    id TEXT NOT NULL,
    phase_id INTEGER NULL,
    day_number INTEGER NULL,
    estrogen TEXT NULL,
    estrogen_trend TEXT NULL,
    progesterone TEXT NULL,
    progesterone_trend TEXT NULL,
    fsh TEXT NULL,
    fsh_trend TEXT NULL,
    lh TEXT NULL,
    lh_trend TEXT NULL,
    mood JSONB NULL,
    energy TEXT NULL,
    best_work_type JSONB NULL,
    created_at TIMESTAMP WITH TIME ZONE NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NULL DEFAULT NOW(),
    CONSTRAINT hormones_data_v2_pkey PRIMARY KEY (id)
) TABLESPACE pg_default;

-- ---------------------------------------------------------------------------
-- nutrition_* / exercises_* — content keyed by hormone_id -> hormones_data_v2(id)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS nutrition_en (
    id TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    hormone_id TEXT NOT NULL REFERENCES hormones_data_v2(id) ON DELETE CASCADE,
    cuisine VARCHAR(100),
    recipe_name VARCHAR(255) NOT NULL,
    image_url TEXT,
    ingredients JSONB,
    steps JSONB,
    nutrients JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nutrition_hi (
    id TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    hormone_id TEXT NOT NULL REFERENCES hormones_data_v2(id) ON DELETE CASCADE,
    cuisine VARCHAR(100),
    recipe_name VARCHAR(255) NOT NULL,
    image_url TEXT,
    ingredients JSONB,
    steps JSONB,
    nutrients JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nutrition_gu (
    id TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    hormone_id TEXT NOT NULL REFERENCES hormones_data_v2(id) ON DELETE CASCADE,
    cuisine VARCHAR(100),
    recipe_name VARCHAR(255) NOT NULL,
    image_url TEXT,
    ingredients JSONB,
    steps JSONB,
    nutrients JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS exercises_en (
    id TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    hormone_id TEXT NOT NULL REFERENCES hormones_data_v2(id) ON DELETE CASCADE,
    category VARCHAR(100) NOT NULL,
    exercise_name VARCHAR(255) NOT NULL,
    image_url TEXT,
    description TEXT,
    steps JSONB,
    energy_level VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS exercises_hi (
    id TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    hormone_id TEXT NOT NULL REFERENCES hormones_data_v2(id) ON DELETE CASCADE,
    category VARCHAR(100) NOT NULL,
    exercise_name VARCHAR(255) NOT NULL,
    image_url TEXT,
    description TEXT,
    steps JSONB,
    energy_level VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS exercises_gu (
    id TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    hormone_id TEXT NOT NULL REFERENCES hormones_data_v2(id) ON DELETE CASCADE,
    category VARCHAR(100) NOT NULL,
    exercise_name VARCHAR(255) NOT NULL,
    image_url TEXT,
    description TEXT,
    steps JSONB,
    energy_level VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Whole foods (still keyed by phase_day string; not FK-enforced to avoid seed ordering constraints)
CREATE TABLE IF NOT EXISTS wholefoods_en (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phase_day_id VARCHAR(10) NOT NULL,
    foods JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS wholefoods_hi (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phase_day_id VARCHAR(10) NOT NULL,
    foods JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS wholefoods_gu (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phase_day_id VARCHAR(10) NOT NULL,
    foods JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_rapidapi_request_id ON users(rapidapi_request_id) WHERE rapidapi_request_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_period_logs_user_id ON period_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_period_logs_date ON period_logs(date);

CREATE INDEX IF NOT EXISTS idx_period_start_logs_user_id ON period_start_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_period_start_logs_start_date ON period_start_logs(start_date);
CREATE INDEX IF NOT EXISTS idx_period_start_logs_user_start ON period_start_logs(user_id, start_date);
CREATE INDEX IF NOT EXISTS idx_period_start_logs_confirmed ON period_start_logs(user_id, is_confirmed) WHERE is_confirmed = TRUE;

CREATE INDEX IF NOT EXISTS idx_user_cycle_days_user_id ON user_cycle_days(user_id);
CREATE INDEX IF NOT EXISTS idx_user_cycle_days_date ON user_cycle_days(date);
CREATE INDEX IF NOT EXISTS idx_user_cycle_days_phase_day_id ON user_cycle_days(phase_day_id);
CREATE INDEX IF NOT EXISTS idx_user_cycle_days_request_id ON user_cycle_days(rapidapi_request_id) WHERE rapidapi_request_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_user_cycle_days_is_predicted ON user_cycle_days(is_predicted);

CREATE INDEX IF NOT EXISTS idx_chat_history_user_id ON chat_history(user_id);

CREATE INDEX IF NOT EXISTS idx_feedback_user_id ON feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON feedback(created_at);

CREATE INDEX IF NOT EXISTS idx_nutrition_en_hormone_id ON nutrition_en(hormone_id);
CREATE INDEX IF NOT EXISTS idx_nutrition_hi_hormone_id ON nutrition_hi(hormone_id);
CREATE INDEX IF NOT EXISTS idx_nutrition_gu_hormone_id ON nutrition_gu(hormone_id);

CREATE INDEX IF NOT EXISTS idx_exercises_en_hormone_id ON exercises_en(hormone_id);
CREATE INDEX IF NOT EXISTS idx_exercises_hi_hormone_id ON exercises_hi(hormone_id);
CREATE INDEX IF NOT EXISTS idx_exercises_gu_hormone_id ON exercises_gu(hormone_id);

CREATE INDEX IF NOT EXISTS idx_wholefoods_en_phase_day_id ON wholefoods_en(phase_day_id);
CREATE INDEX IF NOT EXISTS idx_wholefoods_hi_phase_day_id ON wholefoods_hi(phase_day_id);
CREATE INDEX IF NOT EXISTS idx_wholefoods_gu_phase_day_id ON wholefoods_gu(phase_day_id);

-- ---------------------------------------------------------------------------
-- Row Level Security (user-owned tables only; reference wellness tables rely on service role / open read)
-- ---------------------------------------------------------------------------
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE period_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE period_start_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_cycle_days ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own profile" ON users
    FOR SELECT USING (auth.uid()::text = id::text);

CREATE POLICY "Users can update own profile" ON users
    FOR UPDATE USING (auth.uid()::text = id::text);

CREATE POLICY "Users can insert own profile" ON users
    FOR INSERT WITH CHECK (auth.uid()::text = id::text);

CREATE POLICY "Users can view own period logs" ON period_logs
    FOR SELECT USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can insert own period logs" ON period_logs
    FOR INSERT WITH CHECK (auth.uid()::text = user_id::text);

CREATE POLICY "Users can update own period logs" ON period_logs
    FOR UPDATE USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can delete own period logs" ON period_logs
    FOR DELETE USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can view own period start logs" ON period_start_logs
    FOR SELECT USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can insert own period start logs" ON period_start_logs
    FOR INSERT WITH CHECK (auth.uid()::text = user_id::text);

CREATE POLICY "Users can update own period start logs" ON period_start_logs
    FOR UPDATE USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can delete own period start logs" ON period_start_logs
    FOR DELETE USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can view own cycle days" ON user_cycle_days
    FOR SELECT USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can insert own cycle days" ON user_cycle_days
    FOR INSERT WITH CHECK (auth.uid()::text = user_id::text);

CREATE POLICY "Users can update own cycle days" ON user_cycle_days
    FOR UPDATE USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can delete own cycle days" ON user_cycle_days
    FOR DELETE USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can view own chat history" ON chat_history
    FOR SELECT USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can insert own chat history" ON chat_history
    FOR INSERT WITH CHECK (auth.uid()::text = user_id::text);

CREATE POLICY "Users can view own feedback" ON feedback
    FOR SELECT USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can insert own feedback" ON feedback
    FOR INSERT WITH CHECK (auth.uid()::text = user_id::text);

-- Reference data: enable read for anon/authenticated clients if you expose Supabase directly to the app.
-- Example (uncomment if needed):
-- ALTER TABLE hormones_data ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "Anyone can read hormones reference" ON hormones_data FOR SELECT USING (true);
