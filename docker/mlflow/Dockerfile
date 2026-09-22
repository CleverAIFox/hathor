FROM python:3.12-slim
RUN pip install --no-cache-dir mlflow==3.16.1 psycopg2-binary boto3
EXPOSE 5000
CMD ["sh", "-c", "mlflow server --host 0.0.0.0 --port 5000 \
     --backend-store-uri $MLFLOW_BACKEND_STORE_URI \
     --artifacts-destination $MLFLOW_ARTIFACT_ROOT"]
