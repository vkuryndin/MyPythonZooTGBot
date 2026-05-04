CREATE TABLE IF NOT EXISTS quiz_results (
    id BIGSERIAL PRIMARY KEY,
    telegram_user_id BIGINT NOT NULL,
    username VARCHAR(255),
    full_name VARCHAR(255),
    animal_id VARCHAR(100) NOT NULL,
    animal_name VARCHAR(100) NOT NULL,
    scores JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE quiz_results
ADD COLUMN IF NOT EXISTS image_tags JSONB NOT NULL DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS idx_quiz_results_telegram_user_id
    ON quiz_results (telegram_user_id);

CREATE TABLE IF NOT EXISTS contact_requests (
    id BIGSERIAL PRIMARY KEY,
    telegram_user_id BIGINT NOT NULL,
    username VARCHAR(255),
    full_name VARCHAR(255),
    animal_name VARCHAR(100),
    contact_method VARCHAR(50) NOT NULL,
    message_text TEXT NOT NULL,
    delivery_status VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_contact_requests_telegram_user_id
    ON contact_requests (telegram_user_id);

CREATE TABLE IF NOT EXISTS feedback (
    id BIGSERIAL PRIMARY KEY,
    telegram_user_id BIGINT NOT NULL,
    username VARCHAR(255),
    full_name VARCHAR(255),
    animal_name VARCHAR(100),
    questions_quality INTEGER NOT NULL CHECK (questions_quality BETWEEN 1 AND 5),
    answers_quality INTEGER NOT NULL CHECK (answers_quality BETWEEN 1 AND 5),
    images_quality INTEGER NOT NULL CHECK (images_quality BETWEEN 1 AND 5),
    navigation_quality INTEGER NOT NULL CHECK (navigation_quality BETWEEN 1 AND 5),
    overall_quality INTEGER NOT NULL CHECK (overall_quality BETWEEN 1 AND 5),
    comment_text TEXT,
    telegram_sent BOOLEAN NOT NULL DEFAULT FALSE,
    email_sent BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feedback_telegram_user_id
    ON feedback (telegram_user_id);

CREATE INDEX IF NOT EXISTS idx_contact_requests_created_at_id
    ON contact_requests (created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_feedback_created_at_id
    ON feedback (created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_quiz_results_created_at_id
    ON quiz_results (created_at DESC, id DESC);