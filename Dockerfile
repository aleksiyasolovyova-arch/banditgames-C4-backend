# ---------------------------------------
# 1. Base Image
# ---------------------------------------
FROM python:3.11-slim

# ---------------------------------------
# 2. Set working directory
# ---------------------------------------
WORKDIR /app

# ---------------------------------------
# 3. Install system dependencies
#    - build-essential: for compiling pip packages
#    - curl: for healthcheck
#    - libpq-dev: for psycopg2 (PostgreSQL driver)
# ---------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
 && rm -rf /var/lib/apt/lists/*

# ---------------------------------------
# 4. Copy requirements
# ---------------------------------------
COPY requirements.txt .

# ---------------------------------------
# 5. Install Python dependencies
# ---------------------------------------
RUN pip install --no-cache-dir -r requirements.txt

# ---------------------------------------
# 6. Copy application code
# ---------------------------------------
COPY src ./src

# Create log and data directories
RUN mkdir -p logs data

# ---------------------------------------
# 7. Set a non-root user (good practice)
# ---------------------------------------
RUN useradd -ms /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# ---------------------------------------
# 8. Expose port
# ---------------------------------------
EXPOSE 8000

# ---------------------------------------
# 9. Healthcheck
# ---------------------------------------
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ---------------------------------------
# 10. Start the FastAPI server
# ---------------------------------------
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
