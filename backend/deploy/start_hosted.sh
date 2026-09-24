#!/bin/sh
set -eu

# Render's SQLite disk is mounted at /data. Migrations and seed must run here,
# not in pre-deploy, because pre-deploy containers cannot access the disk.
alembic upgrade head
python -m app.cli seed --if-empty
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
