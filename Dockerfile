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
RUN mkdir -p data/screenshots data/logs \
    && chmod -R 777 data

# Set environment variables
ENV FLASK_APP=app
ENV FLASK_DEBUG=0
ENV DISPLAY=:99
ENV PYTHONUNBUFFERED=1
ENV SELENIUM_HEADLESS=true
# Chrome flags for better extension support in headless mode
ENV CHROME_ARGS="--no-sandbox --disable-dev-shm-usage --disable-gpu --disable-web-security --allow-running-insecure-content --window-size=1920,1080"
ENV DATA_DIR=/app/data
ENV SCREENSHOTS_DIR=/app/data/screenshots

# Create startup script
RUN echo '#!/bin/bash\n\
# Clean any defunct Chrome processes\n\
pkill -9 chrome || true\n\
# Clear browser cache\n\
rm -rf /tmp/* /tmp/.* 2>/dev/null || true\n\
rm -rf ~/.config/google-chrome/ 2>/dev/null || true\n\
# Start virtual display with standard resolution\n\
Xvfb :99 -screen 0 1920x1080x16 -ac > /dev/null 2>&1 &\n\
# Give Xvfb time to start\n\
sleep 3\n\
# Start the Flask application with gunicorn\n\
gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 180 "run:app"\n\
' > /app/startup.sh \
    && chmod +x /app/startup.sh

# Command to run
CMD ["/app/startup.sh"] 