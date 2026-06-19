# Build from the REPO ROOT so the frozen schemas package is in context:
#   docker build -f backend/Dockerfile -t <image> .
FROM python:3.12-slim

WORKDIR /app
COPY schemas/python /app/schemas
COPY backend /app/backend

# Install the frozen contracts first, then the backend (which depends on it).
RUN pip install --no-cache-dir /app/schemas && \
    pip install --no-cache-dir /app/backend

# Production reads real clips from the GCS dictionary bucket (W6).
ENV CLIP_SOURCE=gcs
ENV PORT=8080

# Cloud Run injects $PORT; shell form expands it.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
