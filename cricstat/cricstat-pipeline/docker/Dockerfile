# cricstat-pipeline — scheduled ingestion job. Standard library only, so one stage.
# Build context: cricstat/cricstat-pipeline/
#   docker build -f docker/Dockerfile -t cricstat-pipeline:latest .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    CRICSTAT_HOME=/cricstat

WORKDIR /app
COPY . .

# Python imports need underscored names; the dirs use hyphens for readability.
# -sfn keeps this idempotent however the COPY treats the committed symlinks.
# chmod: on the NAS, Synology ACLs grant access while the POSIX bits are 700. COPY keeps those
# bits, so without this the non-root runtime user (operator UID via compose) cannot read /app.
RUN chmod -R a+rX /app && \
    ln -sfn db-logic db_logic && \
    ln -sfn application-logic application_logic && \
    ln -sfn presentation-logic presentation_logic

RUN useradd -m -u 1000 appuser && \
    mkdir -p /cricstat/data /cricstat/logs && \
    chown -R appuser:appuser /cricstat
USER appuser

# Mount the host's cricstat/data and cricstat/logs here.
VOLUME ["/cricstat/data", "/cricstat/logs"]

ENTRYPOINT ["python3", "-m", "presentation_logic.cli"]
CMD ["recent"]
