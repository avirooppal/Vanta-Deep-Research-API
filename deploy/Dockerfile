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
    PATH="/usr/local/bin:$PATH"

EXPOSE 8000

# Default: migrate then serve
CMD ["sh", "-c", "python scripts/migrate.py && uvicorn api.app:app --host 0.0.0.0 --port 8000 --workers 2"]


# ─── Stage 3: playwright variant (PDF/screenshot features) ──────────────────
# Use this target when PDF export via Playwright is needed:
#   docker build --target playwright -t deep-research-api:playwright .
FROM runtime AS playwright

RUN apt-get update && apt-get install -y --no-install-recommends \
        # Chromium system deps
        libnss3 libasound2 libxss1 libatk-bridge2.0-0 \
        libgtk-3-0 libgbm1 libxcomposite1 libxdamage1 \
    && rm -rf /var/lib/apt/lists/*

RUN playwright install chromium --with-deps
