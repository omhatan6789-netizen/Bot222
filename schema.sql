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


CREATE TABLE IF NOT EXISTS public.global_ranks (
    user_id BIGINT NOT NULL,
    rank_key TEXT NOT NULL CHECK (rank_key IN ('dev', 'dev2')),
    granted_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, rank_key)
);


CREATE TABLE IF NOT EXISTS public.group_ranks (
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    rank_key TEXT NOT NULL CHECK (
        rank_key IN ('owner', 'creator', 'manager', 'admin', 'premium')
    ),
    granted_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (chat_id, user_id, rank_key)
);

CREATE INDEX IF NOT EXISTS idx_group_ranks_chat_rank
    ON public.group_ranks (chat_id, rank_key);


CREATE TABLE IF NOT EXISTS public.group_members (
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    first_name TEXT NOT NULL DEFAULT '',
    username TEXT,
    PRIMARY KEY (chat_id, user_id)
);
