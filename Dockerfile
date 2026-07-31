FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
ENV HERMES_EXECUTION_MODE=dry_run
EXPOSE 8000
CMD ["uvicorn","cano_hermes.api.app:app","--host","0.0.0.0","--port","8000"]
