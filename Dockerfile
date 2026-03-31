# ==========================================
# Stage 1: Builder
# ==========================================
FROM python:3.13-alpine AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ✅ Use apk (Alpine package manager)
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libpq-dev

COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# ==========================================
# Stage 2: Production
# ==========================================
FROM python:3.13-alpine

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ✅ Create non-root user (Alpine way)
RUN addgroup -S appuser && adduser -S appuser -G appuser

# ✅ Install runtime deps
RUN apk add --no-cache \
    libpq

COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

COPY . /app/

RUN mkdir -p /app/staticfiles

# Build-time env
RUN SECRET_KEY="dummy_key_for_build" \
    DATABASE_URL="sqlite://:memory:" \
    python manage.py collectstatic --noinput

RUN chmod +x /app/start.sh && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python manage.py check || exit 1

CMD ["/app/start.sh"]
