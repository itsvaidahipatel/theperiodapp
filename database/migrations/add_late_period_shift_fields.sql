-- Late-period anchor shift (stateless calendar): rate-limited cumulative days
-- applied inside calculate_phase_for_date_range; no phase rows persisted here.

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS late_period_anchor_shift_days integer NOT NULL DEFAULT 0;

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS late_period_last_shift_at timestamptz NULL;

COMMENT ON COLUMN users.late_period_anchor_shift_days IS
  'Days to shift predicted cycle starts forward when the next period is late; capped and rate-limited in app logic.';

COMMENT ON COLUMN users.late_period_last_shift_at IS
  'UTC timestamp of last time late_period_anchor_shift_days was incremented (24h idempotency).';
