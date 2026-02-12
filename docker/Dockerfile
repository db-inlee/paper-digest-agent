# =============================================================================
# Stage 1: Build SvelteKit frontend
# =============================================================================
FROM node:20-alpine AS frontend

WORKDIR /app/notifier/web
COPY notifier/web/package.json notifier/web/package-lock.json* ./
RUN npm ci
COPY notifier/web/ ./
RUN npm run build

# =============================================================================
# Stage 2: Python runtime with backend + built frontend
# =============================================================================
FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Install root project (rtc pipeline)
COPY pyproject.toml ./
COPY src/ ./src/
RUN touch README.md && pip install --no-cache-dir .

# Install notifier (toslack server)
COPY notifier/pyproject.toml ./notifier/
COPY notifier/src/ ./notifier/src/
RUN pip install --no-cache-dir ./notifier

# Copy built frontend
COPY --from=frontend /app/notifier/web/build ./notifier/web/build

# Copy reports data (bundled, will be copied to persistent disk on first run)
COPY reports/ ./reports/

# Copy entrypoint
COPY docker/entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

# Default env — Render injects PORT
ENV REPORT_BASE_DIR=/app/data/reports \
    PYTHONPATH=/app/src \
    SERVER_HOST=0.0.0.0 \
    WEB_BUILD_DIR=/app/notifier/web/build \
    PORT=8080

EXPOSE 8080

CMD ["./entrypoint.sh"]
