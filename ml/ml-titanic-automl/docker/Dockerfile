FROM python:3.10-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# pycaret 3.3.1 pins pyyaml==5.4.1 which has no cp310 wheel.
# Its setup.py breaks with setuptools>=65 (missing cython_sources attribute).
# Pre-downgrade setuptools, then install pyyaml without build isolation so
# the build uses the compatible setuptools instead of pip's isolated env.
RUN pip install --no-cache-dir "setuptools<65" && \
    pip install --user --no-cache-dir --no-build-isolation "pyyaml==5.4.1"

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

COPY . .

ENV PYTHONPATH=/app

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "presentation_logic.api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
