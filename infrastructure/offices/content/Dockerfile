# office-content (F11) -- DESIGN ONLY, not run end-to-end in this pass.
# See README.md in this directory for the intended wiring and why it was
# left at design/scaffold: factory-v5's own `runtime/stage-handlers.yaml` is
# a known, documented gap (skills/factory-v5-contract/SKILL.md) that this
# office would depend on for any real render pipeline invocation, and F11's
# time budget prioritized getting office-analytics and office-ugc *really*
# running over a fourth full end-to-end demo.
FROM starhome/office-base:latest

COPY --chown=office:office task.sh /office/task.sh
USER root
RUN chmod +x /office/task.sh
USER office
