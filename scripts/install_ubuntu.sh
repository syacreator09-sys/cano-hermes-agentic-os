#!/usr/bin/env bash
set -euo pipefail
sudo apt update
sudo apt install -y python3-venv python3-pip git curl docker.io docker-compose-plugin
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
cp -n .env.example .env || true
python scripts/validate.py
