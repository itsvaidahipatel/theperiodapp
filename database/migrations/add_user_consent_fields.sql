-- Legal consent audit fields for onboarding/registration
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS consent_accepted boolean NOT NULL DEFAULT false;

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS consent_timestamp timestamptz NULL;

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS privacy_policy_version text NULL;

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS consent_language text NULL;

COMMENT ON COLUMN users.consent_accepted IS
  'True when user explicitly accepts privacy terms during registration.';

COMMENT ON COLUMN users.consent_timestamp IS
  'UTC timestamp of consent acceptance captured during registration.';

COMMENT ON COLUMN users.privacy_policy_version IS
  'Privacy policy version accepted by the user at registration.';

COMMENT ON COLUMN users.consent_language IS
  'Language choice shown to the user when consent was accepted.';
