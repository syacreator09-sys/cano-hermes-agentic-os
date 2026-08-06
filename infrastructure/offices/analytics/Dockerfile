# office-analytics (F11) — read-only: costos, metricas, auditoria de calidad,
# salud. The safest of the 4 offices: no write access anywhere, no
# credentials beyond tier-0 (KIMI) for its own hermes --oneshot supervisor.
FROM starhome/office-base:latest

COPY --chown=office:office task.sh /office/task.sh
USER root
RUN chmod +x /office/task.sh
USER office
