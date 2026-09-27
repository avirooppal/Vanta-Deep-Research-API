# ─── Stage 1: dependency builder ───────────────────────────────────────────
FROM python:3.12-slim-bookworm AS builder

WORKDIR /app

# System build deps only — not carried into the final image
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libffi-dev \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ─── Stage 2: runtime image ─────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app

# Minimal runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        libffi8 \
        # weasyprint needs pango
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libcairo2 \
        shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source (honoured by .dockerignore)
COPY . .

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/usr/local/bin:$PATH" \
    PORT=8000

RUN chmod +x scripts/*.sh 2>/dev/null || true

EXPOSE ${PORT}

# Cloud & local ready entrypoint
CMD ["sh", "scripts/start_cloud.sh"]
