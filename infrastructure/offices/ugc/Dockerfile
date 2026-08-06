# office-ugc (F11) — F9's UGC-Affiliate free tier, containerized: runs
# ugc-commerce-studio's `plan` CLI (the engine F9 already proposed for this
# office) in dry-run mode (paid_generation: false, no Higgsfield calls) plus
# the hermes --oneshot supervisor.
FROM starhome/office-base:latest

COPY --chown=office:office task.sh /office/task.sh
USER root
RUN chmod +x /office/task.sh
USER office
