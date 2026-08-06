# Ephemeral sandbox worker for container-sandbox skill.
# Rootless, no Docker socket, no capabilities. Only the assigned worktree is
# writable; everything else in the container is read-only.
FROM python:3.12-slim

RUN useradd -m -u 10001 -s /usr/sbin/nologin sandbox
RUN apt-get update && apt-get install -y --no-install-recommends \
        git ffmpeg && rm -rf /var/lib/apt/lists/*

USER sandbox
WORKDIR /workspace

# The worktree is bind-mounted at /workspace by run_container (see run.py).
# No CMD: the executor supplies the exact command per task.
