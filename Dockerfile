# ==========================================
# Stage 1: Build dependencies
# ==========================================
FROM python:3.11-slim as builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .

# Install pip and wheel build requirements
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# ==========================================
# Stage 2: Lean Runtime
# ==========================================
FROM python:3.11-slim as runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create unprivileged system user
RUN useradd -u 1001 -m -s /bin/bash appuser && \
    chown -R appuser:appuser /app

# Copy application source code
COPY --chown=appuser:appuser . /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
