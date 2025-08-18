#!/bin/bash

set -e

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Running database migrations..."
python manage.py makemigrations
python manage.py migrate

echo "Set elastic search indexes"
python manage.py search_index --rebuild -f

echo "Starting Gunicorn..."

: "${GUNICORN_WORKERS:=10}"
: "${GUNICORN_BIND:=0.0.0.0:8000}"
: "${GUNICORN_TIMEOUT:=300}"
: "${DJANGO_SETTINGS_MODULE:=config.settings}"

exec gunicorn \
    --workers="$GUNICORN_WORKERS" \
    --bind="$GUNICORN_BIND" \
    --timeout="$GUNICORN_TIMEOUT" \
    --log-level=info \
    --env DJANGO_SETTINGS_MODULE="$DJANGO_SETTINGS_MODULE" \
    config.wsgi:application