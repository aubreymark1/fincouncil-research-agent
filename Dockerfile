# syntax=docker/dockerfile:1

# ---------- Frontend build ----------
FROM node:20-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- Backend runtime ----------
FROM python:3.11-slim AS backend
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    WORKBENCH_STATIC_DIR=/srv/frontend

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY app /app/app
COPY backend /app/backend
COPY configs /app/configs
COPY data /app/data
COPY fixtures /app/fixtures
COPY prompts /app/prompts
COPY scripts /app/scripts
COPY requirements.txt /app/requirements.txt

COPY --from=frontend /build/frontend/dist /srv/frontend

RUN mkdir -p /app/outputs

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
