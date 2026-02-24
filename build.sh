#!/usr/bin/env bash
set -o errexit
pip install -r requirements.txt
# Download spaCy model (optional; app has fallback if this fails)
python -m spacy download en_core_web_sm 2>/dev/null || true
python manage.py collectstatic --no-input
python manage.py migrate --no-input
