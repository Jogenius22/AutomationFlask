FROM python:3.11-slim

# Install Chrome and dependencies with specific Chrome version for better stability
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

# Verify Chrome installation and version
RUN google-chrome --version

# Create app directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Create data directory structure with proper permissions
RUN mkdir -p data/screenshots data/logs \
    && chmod -R 777 data

# Set environment variables for Chrome optimization
ENV FLASK_APP=app
ENV FLASK_DEBUG=0
ENV DISPLAY=:99
ENV PYTHONUNBUFFERED=1
ENV SELENIUM_HEADLESS=true
# More conservative Chrome flags to prevent crashes
ENV CHROME_ARGS="--no-sandbox --disable-dev-shm-usage --disable-gpu --disable-extensions --single-process --disable-features=VizDisplayCompositor --memory-pressure-off --disable-backing-store-limit --disable-software-rasterizer --disk-cache-size=1 --media-cache-size=1 --disable-application-cache --js-flags=\"--max-old-space-size=256 --expose-gc\" --incognito"
ENV DATA_DIR=/app/data
ENV SCREENSHOTS_DIR=/app/data/screenshots
# Add session recovery limits to prevent cascading failures
ENV MAX_SESSION_RESTARTS=2
ENV SESSION_RESTART_DELAY=10

# Create memory optimization and monitoring script for Chrome
RUN echo '#!/bin/bash\n\
\n\
# Function to clear temp files and defunct processes\n\
function cleanup() {\n\
    echo "Running browser cleanup..."\n\
    # Kill any zombie Chrome processes\n\
    pkill -9 chrome || true\n\
    pkill -9 -f "Xvfb" || true\n\
    # Clear cache and temp files\n\
    rm -rf /tmp/.org.chromium.Chromium* /tmp/.X*-lock /tmp/hsperfdata_* /tmp/*.sock* 2>/dev/null || true\n\
    rm -rf /tmp/* /tmp/.* 2>/dev/null || true\n\
    # Clear Chrome user data\n\
    rm -rf ~/.config/google-chrome/ 2>/dev/null || true\n\
    # Create fresh temp directory\n\
    mkdir -p /tmp\n\
    chmod 1777 /tmp\n\
}\n\
\n\
# Run initial cleanup\n\
cleanup\n\
\n\
# Start virtual display with minimal resolution\n\
echo "Starting Xvfb..."\n\
Xvfb :99 -screen 0 800x600x16 -ac > /dev/null 2>&1 &\n\
XVFB_PID=$!\n\
sleep 2\n\
\n\
# Verify Xvfb is running\n\
if ! ps -p $XVFB_PID > /dev/null; then\n\
    echo "Error: Xvfb failed to start"\n\
    exit 1\n\
fi\n\
\n\
# Set up a periodic cleanup task (every 30 minutes)\n\
(while true; do sleep 1800; cleanup; done) &\n\
\n\
# Function to monitor memory usage\n\
function monitor_resources() {\n\
    while true; do\n\
        mem_total=$(free -m | grep Mem | awk "{print \$2}")\n\
        mem_used=$(free -m | grep Mem | awk "{print \$3}")\n\
        mem_usage=$(( (mem_used * 100) / mem_total ))\n\
        echo "$(date): Memory usage: ${mem_usage}% (${mem_used}MB / ${mem_total}MB)"\n\
        if [ $mem_usage -gt 85 ]; then\n\
            echo "WARNING: High memory usage detected!"\n\
            cleanup\n\
        fi\n\
        sleep 60\n\
    done\n\
}\n\
\n\
# Start resource monitor in the background\n\
monitor_resources &\n\
\n\
# Handle SIGTERM gracefully\n\
function handle_sigterm() {\n\
    echo "Received SIGTERM, shutting down gracefully..."\n\
    pkill -TERM -P $$ || true\n\
    exit 0\n\
}\n\
\n\
trap handle_sigterm SIGTERM\n\
\n\
# Start the Flask application with gunicorn\n\
echo "Starting Flask application..."\n\
gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 180 --graceful-timeout 30 "run:app"\n\
' > /app/startup.sh \
    && chmod +x /app/startup.sh

# Command to run
CMD ["/app/startup.sh"] 