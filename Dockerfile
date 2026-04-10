FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./requirements.txt
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r backend/requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY tools/ ./tools/
COPY ENRICHMENT_API.md ./ENRICHMENT_API.md

# Create tmp directories for cache and processing
RUN mkdir -p .tmp/html .tmp/images .tmp/cache

# Set working directory to backend so relative imports (from api.xxx) work
WORKDIR /app/backend

# Add parent dir to PYTHONPATH so tools/ imports work
ENV PYTHONPATH=/app

EXPOSE ${PORT:-8000}

CMD uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2
