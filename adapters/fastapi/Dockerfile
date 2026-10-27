# Build từ GỐC repo:  docker build -f adapters/fastapi/Dockerfile --build-arg GIT_SHA=$(git rev-parse --short HEAD) -t ccapi:v1 .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY adapters/fastapi/requirements.txt .
RUN pip install -r requirements.txt

COPY core/ccapi_core ./ccapi_core
COPY adapters/fastapi/app.py .

ARG GIT_SHA=dev
ENV GIT_SHA=${GIT_SHA} PORT=8080 STORE=memory

# 1 worker: để so sánh công bằng với Cloud Run (1 vCPU). Cloud Run tự đặt PORT=8080.
CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT} --workers 1"]
