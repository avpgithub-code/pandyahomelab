FROM python:3.11-slim

WORKDIR /mlflow

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000

HEALTHCHECK --interval=10s --timeout=5s \
  CMD python -c "import requests; requests.get('http://localhost:5000/health')" || exit 1

CMD ["mlflow", "server", \
     "--host", "0.0.0.0", \
     "--port", "5000", \
     "--backend-store-uri", "${BACKEND_STORE_URI:-sqlite:///mlflow/mlruns.db}", \
     "--default-artifact-root", "${ARTIFACT_ROOT:-s3://mlflow/artifacts}"]
