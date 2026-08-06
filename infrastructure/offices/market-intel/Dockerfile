# office-market-intel (K9) -- built for real per docs/MARKET_INTEL_OFFICE_DESIGN.md
# (Prometeo F14, design-only at the time). Same base/pattern as the other 4
# offices: never installs hermes itself, only its own read-only task.sh.
FROM starhome/office-base:latest

COPY --chown=office:office task.sh /office/task.sh
USER root
RUN chmod +x /office/task.sh
USER office
