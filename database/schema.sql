-- PeriodCycle.AI Database Schema
-- Run this in your Supabase SQL editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    last_period_date DATE,
    cycle_length INTEGER DEFAULT 28,
    allergies JSONB DEFAULT '[]'::jsonb,
    language VARCHAR(10) DEFAULT 'en',
    favorite_cuisine VARCHAR(100),
    interests JSONB DEFAULT '[]'::jsonb,
    saved_items JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Period logs table
CREATE TABLE IF NOT EXISTS period_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    flow VARCHAR(50),
    mood VARCHAR(50),
    energy_level VARCHAR(50),
    symptoms JSONB DEFAULT '[]'::jsonb,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, date)
);

-- User cycle days table (phase mappings)
CREATE TABLE IF NOT EXISTS user_cycle_days (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    phase VARCHAR(50) NOT NULL,
    phase_day_id VARCHAR(10) NOT NULL,
    PRIMARY KEY (user_id, date)
);

-- Chat history table
CREATE TABLE IF NOT EXISTS chat_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    response TEXT NOT NULL,
    language VARCHAR(10) DEFAULT 'en',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Hormones data table
CREATE TABLE IF NOT EXISTS hormones_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phase_day_id VARCHAR(10) NOT NULL,
    energy_level VARCHAR(50),
    estrogen DECIMAL(10, 2),
    progesterone DECIMAL(10, 2),
    fsh DECIMAL(10, 2),
    lh DECIMAL(10, 2),
    estrogen_trend VARCHAR(10), -- 'up', 'down', 'stable'
    progesterone_trend VARCHAR(10),
    fsh_trend VARCHAR(10),
    lh_trend VARCHAR(10),
    emotional_summary TEXT,
    physical_summary TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Nutrition tables (multi-language)
CREATE TABLE IF NOT EXISTS nutrition_en (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phase_day_id VARCHAR(10) NOT NULL,
    cuisine VARCHAR(100),
    recipe_name VARCHAR(255) NOT NULL,
    image_url TEXT,
    ingredients JSONB,
    steps JSONB,
    nutrients JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nutrition_hi (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phase_day_id VARCHAR(10) NOT NULL,
    cuisine VARCHAR(100),
    recipe_name VARCHAR(255) NOT NULL,
    image_url TEXT,
    ingredients JSONB,
    steps JSONB,
    nutrients JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nutrition_gu (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phase_day_id VARCHAR(10) NOT NULL,
    cuisine VARCHAR(100),
    recipe_name VARCHAR(255) NOT NULL,
    image_url TEXT,
    ingredients JSONB,
    steps JSONB,
    nutrients JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Whole foods tables (multi-language)
CREATE TABLE IF NOT EXISTS wholefoods_en (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phase_day_id VARCHAR(10) NOT NULL,
    foods JSONB NOT NULL, -- [{"name": "Oats", "benefit": "..."}, ...]
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS wholefoods_hi (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phase_day_id VARCHAR(10) NOT NULL,
    foods JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS wholefoods_gu (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phase_day_id VARCHAR(10) NOT NULL,
    foods JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Exercise tables (multi-language)
CREATE TABLE IF NOT EXISTS exercises_en (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phase_day_id VARCHAR(10) NOT NULL,
    category VARCHAR(100) NOT NULL, -- 'Yoga', 'Cardio', 'Strength', 'Mind', etc.
    exercise_name VARCHAR(255) NOT NULL,
    image_url TEXT,
    description TEXT,
    steps JSONB,
    energy_level VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS exercises_hi (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phase_day_id VARCHAR(10) NOT NULL,
    category VARCHAR(100) NOT NULL,
    exercise_name VARCHAR(255) NOT NULL,
    image_url TEXT,
    description TEXT,
    steps JSONB,
    energy_level VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS exercises_gu (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phase_day_id VARCHAR(10) NOT NULL,
    category VARCHAR(100) NOT NULL,
    exercise_name VARCHAR(255) NOT NULL,
    image_url TEXT,
    description TEXT,
    steps JSONB,
    energy_level VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_period_logs_user_id ON period_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_period_logs_date ON period_logs(date);
CREATE INDEX IF NOT EXISTS idx_user_cycle_days_user_id ON user_cycle_days(user_id);
CREATE INDEX IF NOT EXISTS idx_user_cycle_days_date ON user_cycle_days(date);
CREATE INDEX IF NOT EXISTS idx_user_cycle_days_phase_day_id ON user_cycle_days(phase_day_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_user_id ON chat_history(user_id);
CREATE INDEX IF NOT EXISTS idx_hormones_data_phase_day_id ON hormones_data(phase_day_id);
CREATE INDEX IF NOT EXISTS idx_nutrition_en_phase_day_id ON nutrition_en(phase_day_id);
CREATE INDEX IF NOT EXISTS idx_nutrition_hi_phase_day_id ON nutrition_hi(phase_day_id);
CREATE INDEX IF NOT EXISTS idx_nutrition_gu_phase_day_id ON nutrition_gu(phase_day_id);
CREATE INDEX IF NOT EXISTS idx_wholefoods_en_phase_day_id ON wholefoods_en(phase_day_id);
CREATE INDEX IF NOT EXISTS idx_wholefoods_hi_phase_day_id ON wholefoods_hi(phase_day_id);
CREATE INDEX IF NOT EXISTS idx_wholefoods_gu_phase_day_id ON wholefoods_gu(phase_day_id);
CREATE INDEX IF NOT EXISTS idx_exercises_en_phase_day_id ON exercises_en(phase_day_id);
CREATE INDEX IF NOT EXISTS idx_exercises_hi_phase_day_id ON exercises_hi(phase_day_id);
CREATE INDEX IF NOT EXISTS idx_exercises_gu_phase_day_id ON exercises_gu(phase_day_id);

-- Row Level Security (RLS) Policies

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE period_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_cycle_days ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_history ENABLE ROW LEVEL SECURITY;

-- Users table policies
CREATE POLICY "Users can view own profile" ON users
    FOR SELECT USING (auth.uid()::text = id::text);

CREATE POLICY "Users can update own profile" ON users
    FOR UPDATE USING (auth.uid()::text = id::text);

CREATE POLICY "Users can insert own profile" ON users
    FOR INSERT WITH CHECK (auth.uid()::text = id::text);

-- Period logs policies
CREATE POLICY "Users can view own period logs" ON period_logs
    FOR SELECT USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can insert own period logs" ON period_logs
    FOR INSERT WITH CHECK (auth.uid()::text = user_id::text);

CREATE POLICY "Users can update own period logs" ON period_logs
    FOR UPDATE USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can delete own period logs" ON period_logs
    FOR DELETE USING (auth.uid()::text = user_id::text);

-- User cycle days policies
CREATE POLICY "Users can view own cycle days" ON user_cycle_days
    FOR SELECT USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can insert own cycle days" ON user_cycle_days
    FOR INSERT WITH CHECK (auth.uid()::text = user_id::text);

CREATE POLICY "Users can update own cycle days" ON user_cycle_days
    FOR UPDATE USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can delete own cycle days" ON user_cycle_days
    FOR DELETE USING (auth.uid()::text = user_id::text);

-- Chat history policies
CREATE POLICY "Users can view own chat history" ON chat_history
    FOR SELECT USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can insert own chat history" ON chat_history
    FOR INSERT WITH CHECK (auth.uid()::text = user_id::text);

-- Note: For development, you may want to disable RLS temporarily or use service_role key
-- For production, ensure proper RLS policies are in place

