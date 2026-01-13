# =============================================================================
# AUTODIALER PRO - DOCKERFILE
# =============================================================================

FROM python:3.11-slim

# Labels
LABEL maintainer="WellTech"
LABEL description="Autodialer Pro - Professional autodialer tizimi"

# Environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Tashkent

# Working directory
WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY src/ ./src/
COPY config/ ./config/

# Create directories
RUN mkdir -p audio logs

# Run
CMD ["python", "src/autodialer.py"]
