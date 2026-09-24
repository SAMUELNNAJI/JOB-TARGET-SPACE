#!/usr/bin/env bash
# build.sh — Render build script for JobSpace
set -o errexit   # exit immediately on any error

pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --noinput
python manage.py migrate --noinput
