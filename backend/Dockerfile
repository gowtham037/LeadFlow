FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# App code (repo root mounted to /app so `backend.app.*` imports work)
COPY backend /app/backend


EXPOSE 8002

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8002"]
