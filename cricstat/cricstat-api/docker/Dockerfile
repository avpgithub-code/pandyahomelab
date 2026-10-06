# cricstat-api — always-on, GET-only stats API (F5). Reads the serving DB read-only.
# Build context: cricstat/ (the image also carries docs/validation/golden-selection.csv for the
# admin golden view, P0.3b)
#   docker build -f cricstat-api/docker/Dockerfile -t cricstat-api:latest .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    CRICSTAT_HOME=/cricstat

WORKDIR /app
COPY cricstat-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY cricstat-api/ .
COPY docs/validation/golden-selection.csv /cricstat/docs/validation/golden-selection.csv

# chmod: on the NAS, Synology ACLs grant access while the POSIX bits are 700. COPY keeps those
# bits, so without this the non-root runtime user (operator UID via compose) cannot read /app.
# -sfn: Python imports need the underscored names; the folders use hyphens.
RUN chmod -R a+rX /app /cricstat/docs && \
    ln -sfn db-logic db_logic && \
    ln -sfn application-logic application_logic && \
    ln -sfn presentation-logic presentation_logic && \
    useradd -m -u 1000 appuser && mkdir -p /cricstat/data/db /cricstat/logs
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/v1/health', timeout=4)" || exit 1

# One worker: the NAS memory budget is ~0.5 GB for always-on cricstat (F6 §2); sync endpoints
# run in its thread pool. --proxy-headers: Nginx is the only client.
CMD ["uvicorn", "presentation_logic.api.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-server-header"]
