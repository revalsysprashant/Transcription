#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Explicit file list keeps credentials, recordings, and local dependencies out.
tar -czf deploy/transcription.tar.gz \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='backend/app/storage' \
  compose.production.yml \
  Dockerfile .dockerignore backend/pyproject.toml backend/uv.lock \
  backend/alembic.ini backend/alembic \
  backend/app \
  frontend/Caddyfile \
  frontend/package.json frontend/pnpm-lock.yaml frontend/index.html \
  frontend/tsconfig.json frontend/tsconfig.app.json frontend/tsconfig.node.json \
  frontend/vite.config.ts frontend/src \
  deploy/Caddyfile deploy/install-docker-ubuntu.sh deploy/README.md
echo 'Created deploy/transcription.tar.gz. Transfer .env.production separately over SSH.'
