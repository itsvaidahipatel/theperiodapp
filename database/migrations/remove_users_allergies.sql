-- Remove allergies from users (no longer used by the app)
ALTER TABLE users
  DROP COLUMN IF EXISTS allergies;
