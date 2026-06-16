#!/bin/bash
# Build script for Vercel deployment
#
# This runs AFTER pip install (handled by @vercel/python builder)
# and BEFORE the serverless function is packaged.
#
# Configura esto en Vercel Dashboard > Project > Settings > Build Command:
#   bash vercel_build.sh
#
# O configuralo en vercel.json con:
#   "buildCommand": "bash vercel_build.sh"

set -euo pipefail

echo "🏥 Centro de Salud — Vercel Build"
echo "=================================="

# Collect static files for Whitenoise
echo "→ Collecting static files..."
DJANGO_SETTINGS_MODULE=config.settings.production \
  python manage.py collectstatic --noinput --clear

echo "✅ Build complete"
