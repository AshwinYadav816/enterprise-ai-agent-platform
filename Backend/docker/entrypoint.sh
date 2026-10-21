#!/bin/sh
# Container start: apply migrations, then serve. Behind a reverse proxy set FORWARDED_ALLOW_IPS
# to the proxy's address so client IPs (rate limits, audit log) come from X-Forwarded-For.
set -e
alembic upgrade head
exec uvicorn app.main:create_app --factory \
    --host 0.0.0.0 --port "${PORT:-8000}" \
    --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}"
