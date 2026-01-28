# 1. BASE IMAGE
FROM python:3.11-slim-bullseye 

# 2. ENVIRONMENT SETUP
WORKDIR /app
ENV PYTHONUNBUFFERED=1

# 3. INSTALL SYSTEM DEPENDENCIES FOR PLAYWRIGHT/CHROMIUM
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libglib2.0-0 libnspr4 libnss3 libdbus-1-3 libatk1.0-0 \
        libatk-bridge2.0-0 libatspi2.0-0 libx11-6 libxcomposite1 \
        libxdamage1 libxext6 libxfixes3 libxrandr2 libgbm1 \
        libxcb1 libxkbcommon0 libasound2 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 4. INSTALL PYTHON DEPENDENCIES
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. INSTALL BROWSER BINARIES
# This is required for Playwright to work inside the container
RUN playwright install chromium --with-deps

# 6. COPY APPLICATION CODE
COPY . /app/

# 7. DEFINE THE START COMMAND
# Points to main.py inside the worker folder
CMD ["python", "-u", "worker/main.py"]
