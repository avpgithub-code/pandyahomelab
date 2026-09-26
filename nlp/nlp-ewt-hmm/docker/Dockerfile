# Build stage — install deps with build tools available.
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# spaCy's small English model, pinned to the release matching spacy 3.7.x, so
# warm-up never downloads anything.
RUN pip install --no-cache-dir \
    https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl

# Runtime stage — slim base + copied site-packages, no build tools.
FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
ENV PYTHONPATH=/app
# Silence mlflow's gitpython warning — there's no git repo inside the container.
ENV GIT_PYTHON_REFRESH=quiet

COPY . .

# Python imports need underscored names; the dirs use hyphens for portfolio
# readability. -sf keeps this idempotent however the COPY treats symlinks.
RUN ln -sf db-logic db_logic && \
    ln -sf application-logic application_logic && \
    ln -sf presentation-logic presentation_logic

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# python:slim has no curl — probe with urllib. start-period covers warm-up
# training; raise it (and the compose healthcheck) if the demo trains longer.
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "presentation_logic.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
