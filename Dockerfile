# ---------------------------------------
# 1. Base Image
# ---------------------------------------
FROM python:3.11-slim

# ---------------------------------------
# 2. Set working directory
# ---------------------------------------
WORKDIR /app

# ---------------------------------------
# 3. Install system dependencies (optional)
#    gcc is often needed for some pip packages
# ---------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
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
COPY app ./app

# Create log directory
RUN mkdir -p logs

# ---------------------------------------
# 7. Set a non-root user (good practice)
# ---------------------------------------
RUN useradd -ms /bin/bash appuser
USER appuser

# ---------------------------------------
# 8. Expose port
# ---------------------------------------
EXPOSE 8000

# ---------------------------------------
# 9. Start the FastAPI server
# ---------------------------------------
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
