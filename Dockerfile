# 1. BASE IMAGE
FROM python:3.11-slim-bullseye

# 2. ENVIRONMENT SETUP
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PORT=8080 \
    AUTO_START_BOT=true

# 3. INSTALL MINIMAL SYSTEM DEPENDENCIES FIRST
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        wget \
        curl \
        gnupg \
        ca-certificates \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 4. INSTALL PYTHON DEPENDENCIES
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5. INSTALL PLAYWRIGHT SYSTEM DEPENDENCIES AUTOMATICALLY
# This is the key fix - let Playwright install its own dependencies
RUN playwright install-deps chromium

# 6. INSTALL BROWSER BINARIES
RUN playwright install chromium

# 7. COPY APPLICATION CODE
COPY . /app/

# 8. CREATE PROPER PYTHON PACKAGE STRUCTURE
RUN touch /app/worker/__init__.py && \
    touch /app/worker/esd/__init__.py

# 9. CREATE NON-ROOT USER
RUN groupadd -r appuser && useradd -r -g appuser appuser && \
    chown -R appuser:appuser /app
USER appuser

# 10. EXPOSE PORT
EXPOSE 8080

# 11. START COMMAND
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "--timeout", "0", "worker.main:app"]