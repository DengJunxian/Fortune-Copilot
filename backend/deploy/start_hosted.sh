#!/bin/sh
set -eu

# The free web container is ephemeral; DATABASE_URL must point to persistent
# PostgreSQL. Keep migrations and idempotent synthetic seeding on startup.
alembic upgrade head
python -m app.cli seed --if-empty
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
