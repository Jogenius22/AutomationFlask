FROM python:3.11-slim

# Install Chrome and dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg2 \
    xvfb \
    unzip \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    libxshmfence1 \
    xdg-utils \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Create data directory structure
RUN mkdir -p data/screenshots

# Set environment variables
ENV FLASK_APP=app
ENV FLASK_DEBUG=0
ENV DISPLAY=:99
ENV PYTHONUNBUFFERED=1
ENV SELENIUM_HEADLESS=true
ENV CHROME_ARGS="--no-sandbox --disable-dev-shm-usage --disable-gpu --disable-extensions --disable-software-rasterizer --disable-setuid-sandbox --single-process --disable-features=VizDisplayCompositor,NetworkService,NetworkServiceInProcess --memory-pressure-off --disable-backing-store-limit --js-flags=\"--max-old-space-size=128\""
ENV DATA_DIR=/app/data
ENV SCREENSHOTS_DIR=/app/data/screenshots

# Create memory optimization script for Chrome
RUN echo '#!/bin/bash\n\
# Clean any defunct Chrome processes\n\
pkill -9 chrome || true\n\
# Clear browser cache periodically\n\
rm -rf /tmp/* /tmp/.* 2>/dev/null || true\n\
# Start virtual display with minimal resolution\n\
Xvfb :99 -screen 0 1024x768x16 -ac > /dev/null 2>&1 &\n\
# Start the Flask application with gunicorn\n\
gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 120 "run:app"\n\
' > /app/startup.sh \
    && chmod +x /app/startup.sh

# Command to run
CMD ["/app/startup.sh"] 