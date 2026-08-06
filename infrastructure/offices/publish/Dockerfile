# office-publish (F11) -- DESIGN ONLY, not run end-to-end in this pass.
# Never receives real publish credentials -- see README.md.
FROM starhome/office-base:latest

COPY --chown=office:office task.sh /office/task.sh
USER root
RUN chmod +x /office/task.sh
USER office
