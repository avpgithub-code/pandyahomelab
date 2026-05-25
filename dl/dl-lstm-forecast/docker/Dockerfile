# Build stage — install all deps (torch CPU wheels are large; isolate from runtime).
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# --extra-index-url for the CPU-only torch wheels is the first line of requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

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
# readability. -sf overwrites any symlink the COPY may have brought along, so
# this step is idempotent regardless of how Docker handles symlinks in the
# build context.
RUN ln -sf db-logic db_logic && \
    ln -sf application-logic application_logic && \
    ln -sf presentation-logic presentation_logic

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# PyTorch cold-import is slow (~10s); --start-period gives the container time
# to bind to :8000 before the first healthcheck attempt counts as a failure.
# LSTM training also runs in the warm-up thread for ~10s on top of that.
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "presentation_logic.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
