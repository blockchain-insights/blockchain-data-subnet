-- init_migration_tracking.sql
CREATE TABLE IF NOT EXISTS migration_tracking (
    id SERIAL PRIMARY KEY,
    script_name VARCHAR(255) UNIQUE NOT NULL,
    executed_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);
