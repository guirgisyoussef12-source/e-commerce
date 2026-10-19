# =========================
# Stage 1: Builder
# =========================

FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1


# Install build dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*


# Copy only dependencies first for caching
COPY requirements.txt .


# Build wheels
RUN pip wheel \
    --no-cache-dir \
    --no-deps \
    -r requirements.txt \
    -w /wheels



# =========================
# Stage 2: Production
# =========================

FROM python:3.12-slim AS production

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1


# Install runtime dependency for PostgreSQL
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*


# Copy built wheels from builder
COPY --from=builder /wheels /wheels


# Install python dependencies
RUN pip install \
    --no-cache-dir \
    /wheels/*


# Copy application
COPY . .


# Create non-root user
RUN adduser \
    --disabled-password \
    --gecos "" \
    django-user \
    && chown -R django-user:django-user /app


USER django-user


EXPOSE 8000


CMD ["gunicorn", "ecommerce.wsgi:application", "--bind", "0.0.0.0:8000"]
