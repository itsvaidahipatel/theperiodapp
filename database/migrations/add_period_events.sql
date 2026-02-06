-- Migration: Add PeriodStartLog table
-- This creates a stable, derived layer for cycle start dates
-- 
-- DESIGN: One log = one cycle start (period start only, no end/duration)
-- This is simpler and medically valid (doctors track LMP - Last Menstrual Period)
-- 
-- Core truth: PeriodStartLog = cycle start date
-- Everything else (cycle length, ovulation, predictions) is derived

CREATE TABLE IF NOT EXISTS period_start_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    start_date DATE NOT NULL,
    is_confirmed BOOLEAN DEFAULT TRUE,  -- false for future/predicted logs
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, start_date)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_period_start_logs_user_id ON period_start_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_period_start_logs_start_date ON period_start_logs(start_date);
CREATE INDEX IF NOT EXISTS idx_period_start_logs_user_start ON period_start_logs(user_id, start_date);
CREATE INDEX IF NOT EXISTS idx_period_start_logs_confirmed ON period_start_logs(user_id, is_confirmed) WHERE is_confirmed = TRUE;

-- Enable RLS
ALTER TABLE period_start_logs ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Users can view own period start logs" ON period_start_logs
    FOR SELECT USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can insert own period start logs" ON period_start_logs
    FOR INSERT WITH CHECK (auth.uid()::text = user_id::text);

CREATE POLICY "Users can update own period start logs" ON period_start_logs
    FOR UPDATE USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can delete own period start logs" ON period_start_logs
    FOR DELETE USING (auth.uid()::text = user_id::text);

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_period_start_logs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER period_start_logs_updated_at
    BEFORE UPDATE ON period_start_logs
    FOR EACH ROW
    EXECUTE FUNCTION update_period_start_logs_updated_at();
