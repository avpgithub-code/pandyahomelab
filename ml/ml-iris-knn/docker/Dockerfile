FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
ENV PYTHONPATH=/app

# Copy application code
COPY . .

# Create symlinks for Python imports (folders use hyphens, Python needs underscores)
RUN ln -s /app/db-logic /app/db_logic && \
    ln -s /app/application-logic /app/application_logic && \
    ln -s /app/presentation-logic /app/presentation_logic

# Non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "presentation_logic.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
