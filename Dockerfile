# 1. BASE IMAGE
FROM python:3.11-slim-bullseye

# 2. ENVIRONMENT SETUP
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PORT=8080 \
    AUTO_START_BOT=true \
    PYTHONPATH=/app

# 3. INSTALL SYSTEM DEPENDENCIES FOR PLAYWRIGHT/CHROMIUM
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        wget \
        gnupg \
        ca-certificates \
        fonts-liberation \
        libappindicator3-1 \
        libasound2 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libcups2 \
        libdbus-1-3 \
        libgdk-pixbuf2.0-0 \
        libgtk-3-0 \
        libnspr4 \
        libnss3 \
        libx11-6 \
        libxcomposite1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxrandr2 \
        libxss1 \
        libxtst6 \
        xdg-utils \
        libgbm1 \
        libdrm2 \
        libxkbcommon0 \
        ttf-freefont \
        fonts-noto-color-emoji \
        fonts-freefont-ttf \
        # Additional dependencies for better stability
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libcairo2 \
        libgstreamer1.0-0 \
        libgstreamer-plugins-base1.0-0 \
        libopenh264-6 \
        libopus0 \
        # For Firebase/Firestore
        curl \
        git \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# 4. INSTALL PYTHON DEPENDENCIES
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5. INSTALL BROWSER BINARIES
RUN playwright install chromium --with-deps

# 6. COPY APPLICATION CODE
COPY . /app/

# 7. CREATE PROPER PYTHON PACKAGE STRUCTURE
# Make worker a proper package
RUN touch /app/worker/__init__.py && \
    touch /app/worker/esd/__init__.py

# 8. CREATE NON-ROOT USER FOR SECURITY
RUN groupadd -r appuser && useradd -r -g appuser appuser && \
    chown -R appuser:appuser /app
USER appuser

# 9. HEALTH CHECK
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import requests; r = requests.get('http://localhost:$PORT/health', timeout=5); exit(0) if r.status_code == 200 else exit(1)"

# 10. EXPOSE PORT
EXPOSE 8080

# 11. START COMMAND
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "0", "--access-logfile", "-", "--error-logfile", "-", "worker.main:app"]