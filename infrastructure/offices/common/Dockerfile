# Base image shared by the 4 Prometeo "offices" (F11).
#
# Deliberately thin: python:3.12-slim + the bare minimum to (a) run each
# office's own read-only pipeline step and (b) shell out to the *real*
# `hermes --oneshot` binary, which is never installed inside the image —
# it is bind-mounted read-only from the host at container start (see
# infrastructure/offices/docker-compose.yml). That keeps this image small,
# avoids re-vendoring hermes-agent's ~550MB checkout into every office layer,
# and matches how hermes-agent is already run natively on this host (its own
# venv points at a self-contained uv-managed CPython 3.11 build, portable
# across glibc-based distros).
#
# Runs as a non-root, no-login user (uid 10001), same convention as
# skills/container-sandbox/worker/Dockerfile (F3) — no office needs root.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates tini \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 10001 -d /office -s /usr/sbin/nologin office
WORKDIR /office
ENV HOME=/office \
    PYTHONUNBUFFERED=1 \
    OFFICE_HOME=/office

COPY entrypoint.sh /office/entrypoint.sh
RUN chmod +x /office/entrypoint.sh && \
    mkdir -p /office/output /office/state /office/hermes-home/kanban/boards && \
    chown -R office:office /office

USER office
ENTRYPOINT ["/usr/bin/tini", "--", "/office/entrypoint.sh"]
