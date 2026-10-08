# cricstat-models — scheduled job: Elo ratings, World Cup simulation, daily forecast, weekly training.
# Standard library only (no numpy: the NAS CPU has no AVX, and the job doesn't need it), so one stage.
# Build context: cricstat/ (the job reads the reviewed venue map in cricstat/sql/)
#   docker build -f cricstat-models/docker/Dockerfile -t cricstat-models:latest .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    CRICSTAT_HOME=/cricstat \
    CRICSTAT_MLFLOW_URI=http://ml-mlflow:5000

WORKDIR /app
# Code plus the reviewed inputs that ship with it: supplement/, tournaments/, ratings/.
COPY cricstat-models/ .
COPY sql/venue_map.csv /cricstat/sql/venue_map.csv

# Python imports need underscored names; the dirs use hyphens for readability.
# chmod: on the NAS, Synology ACLs grant access while the POSIX bits are 700 (F6 gotcha).
RUN rm -rf tests .ruff_cache .pytest_cache && \
    chmod -R a+rX /app /cricstat/sql && \
    ln -sfn db-logic db_logic && \
    ln -sfn application-logic application_logic && \
    ln -sfn presentation-logic presentation_logic

RUN useradd -m -u 1000 appuser && \
    mkdir -p /cricstat/data /cricstat/logs && \
    chown -R appuser:appuser /cricstat/data /cricstat/logs
USER appuser

# Mount the host's cricstat/data (serving DB read, forecast.sqlite + data/models written) and logs.
VOLUME ["/cricstat/data", "/cricstat/logs"]

ENTRYPOINT ["python3", "-m", "presentation_logic.cli"]
CMD ["selftest"]
