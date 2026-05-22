-- FridgeChef 초기 스키마 (SDD §2 클래스 다이어그램 → 테이블)
-- Alembic 으로 관리 예정이지만, psql 일회 적용용 raw SQL 도 제공.

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    nickname        VARCHAR(64)  NOT NULL,
    allergies                           JSONB NOT NULL DEFAULT '[]'::jsonb,
    preferences                         JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_email_verified                   BOOLEAN NOT NULL DEFAULT FALSE,
    email_verification_token            VARCHAR(128),
    email_verification_token_expires_at TIMESTAMPTZ,
    created_at                          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);

CREATE TABLE IF NOT EXISTS fridge_items (
    id               SERIAL PRIMARY KEY,
    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    raw_name         VARCHAR(128) NOT NULL,
    normalized_name  VARCHAR(128) NOT NULL,
    quantity         VARCHAR(64),
    expires_at       TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_fridge_items_user_id ON fridge_items (user_id);
CREATE INDEX IF NOT EXISTS ix_fridge_items_normalized ON fridge_items (normalized_name);

CREATE TABLE IF NOT EXISTS recipes (
    id                SERIAL PRIMARY KEY,
    recipe_id         VARCHAR(64) UNIQUE NOT NULL,
    name              VARCHAR(255) NOT NULL,
    whole_ingredients JSONB NOT NULL,
    steps             JSONB NOT NULL DEFAULT '[]'::jsonb,
    cook_min          INTEGER NOT NULL DEFAULT 30,
    spicy             INTEGER NOT NULL DEFAULT 1,
    difficulty_level  INTEGER NOT NULL DEFAULT 1,
    is_low_calorie    BOOLEAN NOT NULL DEFAULT FALSE,
    country           VARCHAR(8)  NOT NULL DEFAULT 'kr',
    theme             VARCHAR(16) NOT NULL DEFAULT 'main',
    allergens         JSONB NOT NULL DEFAULT '[]'::jsonb,
    image_url         TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_recipes_recipe_id ON recipes (recipe_id);

CREATE TABLE IF NOT EXISTS ratings (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recipe_id   VARCHAR(64) NOT NULL,
    score       INTEGER NOT NULL CHECK (score BETWEEN 1 AND 5),
    comment     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_ratings_user_id   ON ratings (user_id);
CREATE INDEX IF NOT EXISTS ix_ratings_recipe_id ON ratings (recipe_id);
