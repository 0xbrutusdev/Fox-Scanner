FROM python:3.12-slim-bookworm

WORKDIR /app

COPY backend/foxscanner /app/backend/foxscanner
COPY backend/requirements.txt /app/backend/requirements.txt
COPY frontend /app/frontend

RUN mkdir -p /var/data \
    && rm -rf /app/backend/foxscanner/**/__pycache__

WORKDIR /app/backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    HOST=0.0.0.0

EXPOSE 8080

CMD ["python", "-u", "-m", "foxscanner"]
