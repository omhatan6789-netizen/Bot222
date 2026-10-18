CREATE TABLE IF NOT EXISTS public.bot_users (
    user_id BIGINT PRIMARY KEY,
    first_name TEXT NOT NULL DEFAULT '',
    username TEXT,
    message_count BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bot_users_username
    ON public.bot_users (LOWER(username));
