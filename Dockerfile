# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Create a non-root user
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Expose the port
EXPOSE 8000

# Use the start script or fallback to gunicorn directly
CMD ["sh", "-c", "if [ -f start.sh ]; then chmod +x start.sh && ./start.sh; else gunicorn src.app:app --bind 0.0.0.0:${PORT:-8000} --workers 1 --timeout 120; fi"]