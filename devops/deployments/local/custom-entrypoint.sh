#!/bin/bash
# custom-entrypoint.sh

# Function to run a migration script
run_migration() {
    local script=$1
    echo "Running migration script: $script"
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "/migrations/$script"
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
         "INSERT INTO migration_tracking (script_name) VALUES ('$script');"
}

# Wait for the PostgreSQL server to start
until pg_isready -h localhost -U "$POSTGRES_USER" -d "$POSTGRES_DB" -q; do
  echo "Waiting for PostgreSQL to start..."
  sleep 1
done

echo "PostgreSQL started."

# Run the initial script to set up migration tracking (if not already set up)
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "/migrations/init_migration_tracking.sql"

# Get the list of migration scripts that have not been executed
migrations_to_run=$(psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
                   "SELECT script FROM pg_ls_dir('/migrations') \
                    WHERE script <> 'init_migration_tracking.sql' \
                    AND script NOT IN (SELECT script_name FROM migration_tracking) \
                    ORDER BY script;")

# Run each migration script that has not been executed
echo "$migrations_to_run" | while read -r script; do
  if [[ -n "$script" ]]; then
    run_migration "$script"
  fi
done

# Call the original entrypoint script to start PostgreSQL normally
exec docker-entrypoint.sh postgres
