#!/usr/bin/env bash
# Builds the shared starhome/office-base:latest image that every office's
# own Dockerfile (analytics/, ugc/, content/, publish/) is FROM. Compose
# doesn't know about this dependency automatically (it's not a compose
# service, on purpose -- it's never run by itself), so build it once before
# `docker compose build`/`up` on any office.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
docker build -t starhome/office-base:latest ./common
