# ----------------------------------------------------
# 1. BASE IMAGE
# ----------------------------------------------------
FROM python:3.11-slim-bullseye 

# ----------------------------------------------------
# 2. ENVIRONMENT SETUP FOR CLOUD RUN
# ----------------------------------------------------
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PORT=8080 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# ----------------------------------------------------
# 3. INSTALL SYSTEM DEPENDENCIES FOR PLAYWRIGHT
# ----------------------------------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libnspr4 \
        libnss3 \
        libdbus-1-3 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libatspi2.0-0 \
        libx11-6 \
        libxcomposite1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libxcb1 \
        libxkbcommon0 \
        libasound2 \
        # Additional dependencies for better compatibility
        wget \
        curl \
        ca-certificates \
        fonts-liberation \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# ----------------------------------------------------
# 4. INSTALL PYTHON DEPENDENCIES
# ----------------------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ----------------------------------------------------
# 5. INSTALL PLAYWRIGHT BROWSER
# ----------------------------------------------------
RUN playwright install chromium

# ----------------------------------------------------
# 6. CREATE PROPER PACKAGE STRUCTURE
# ----------------------------------------------------
RUN touch /app/worker/__init__.py && \
    touch /app/worker/esd/__init__.py

# ----------------------------------------------------
# 7. COPY APPLICATION CODE
# ----------------------------------------------------
COPY . /app/

# ----------------------------------------------------
# 8. CREATE NON-ROOT USER (Security best practice)
# ----------------------------------------------------
RUN groupadd -r appuser && useradd -r -g appuser appuser && \
    chown -R appuser:appuser /app
USER appuser

# ----------------------------------------------------
# 9. EXPOSE PORT (Cloud Run requirement)
# ----------------------------------------------------
EXPOSE 8080

# ----------------------------------------------------
# 10. DEFINE START COMMAND FOR CLOUD RUN
# Use gunicorn as production server
# ----------------------------------------------------
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "0", "worker.main:app"]