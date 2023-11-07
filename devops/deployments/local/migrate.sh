#!/bin/bash
# migrate.sh

# Stop on error
set -e

# Set the PGPASSWORD environment variable so psql doesn't prompt for a password
export PGPASSWORD="$POSTGRES_PASSWORD"

# Function to run a migration script
run_migration() {
    local script=$1
    echo "Running migration script: $script"
    # Run the script with psql
    psql -h postgres -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "/migrations/$script" || {
        echo "Failed to run migration: $script"
        exit 1
    }
    # Record the migration
    psql -h postgres -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
         "INSERT INTO migration_tracking (script_name) VALUES ('$script') ON CONFLICT (script_name) DO NOTHING;" || {
        echo "Failed to record migration: $script"
        exit 1
    }
}

# Wait for the PostgreSQL server to start
until pg_isready -h postgres -U "$POSTGRES_USER" -d "$POSTGRES_DB" -q; do
  echo "Waiting for PostgreSQL to start..."
  sleep 1
done

echo "PostgreSQL started."

# Run the initial script to set up migration tracking (if not already set up)
psql -h postgres -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "/migrations/init_migration_tracking.sql"

# Iterate over each SQL file in the /migrations directory
for script in /migrations/*.sql; do
    # Extract just the filename from the path
    script_name=$(basename "$script")

    # Skip the init_migration_tracking.sql script
    if [ "$script_name" = "init_migration_tracking.sql" ]; then
        continue
    fi

    # Check if the script has already been executed
    script_executed=$(psql -h postgres -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
                     "SELECT EXISTS(SELECT 1 FROM migration_tracking WHERE script_name = '$script_name');")

    # Trim whitespace for the check
    script_executed=$(echo "$script_executed" | xargs)

    # If the script has not been executed, run it
    if [ "$script_executed" = "f" ]; then
        run_migration "$script_name"
    else
        echo "Skipping already executed script: $script_name"
    fi
done

echo "All migrations executed successfully."
