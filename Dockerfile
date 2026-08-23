# Production Dockerfile for Health Buddy Medical Chatbot (Render-optimized)
FROM python:3.11-slim

# Set environment variables (restrict thread pools to prevent memory spikes on 512MB RAM)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FLASK_ENV=production \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    TORCH_NUM_THREADS=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 appuser

# Copy requirements file (Render-specific: excludes PyTorch to stay under 512MB)
COPY requirements-render.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements-render.txt

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8080

# Health check using dynamic PORT environment variable
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os, urllib.request; port=os.environ.get('PORT', '8080'); urllib.request.urlopen(f'http://localhost:{port}/health', timeout=5)" || exit 1

# Run with gunicorn:
#   --preload: loads the app in the master process BEFORE forking workers,
#              so the port binds immediately (fixes Render's port scan timeout)
#   --workers 1 --threads 2: minimal footprint for 512MB RAM
#   --worker-class gthread: explicit threaded worker class
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 2 --worker-class gthread --preload --timeout 120 --access-logfile - --error-logfile - wsgi:app"]