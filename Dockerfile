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

# Create persistent data directory structure
# This directory will be mounted as a volume in production
RUN mkdir -p /app/data/screenshots /app/data/logs /app/data/uploads \
    && chmod -R 777 /app/data

# Create /tmp/.X11-unix directory and set permissions
# This helps with Xvfb and Chrome issues in headless mode
RUN mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix

# Set environment variables
ENV FLASK_APP=app
ENV FLASK_DEBUG=0
ENV DISPLAY=:99
ENV PYTHONUNBUFFERED=1
ENV SELENIUM_HEADLESS=true
# Chrome flags for better extension support in headless mode
ENV CHROME_ARGS="--no-sandbox --disable-dev-shm-usage --disable-gpu --disable-web-security --allow-running-insecure-content --window-size=1920,1080 --remote-debugging-port=9222"
# Ensure proper paths
ENV DATA_DIR=/app/data
# Set HOME directory for Chrome
ENV HOME=/tmp/chrome

# Create startup script with improved error handling and data directory checks
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Print environment for debugging\n\
echo "Starting container with:"\n\
echo "- Data directory: $DATA_DIR"\n\
echo "- Display: $DISPLAY"\n\
echo "- Chrome args: $CHROME_ARGS"\n\
\n\
# Ensure data directories exist and have correct permissions\n\
mkdir -p "$DATA_DIR/screenshots" "$DATA_DIR/logs" "$DATA_DIR/uploads"\n\
chmod -R 777 "$DATA_DIR"\n\
echo "✅ Data directory structure verified"\n\
\n\
# Create Chrome user directory in /tmp and set permissions\n\
mkdir -p /tmp/chrome\n\
chmod -R 777 /tmp/chrome\n\
echo "✅ Chrome temp directory created"\n\
\n\
# Create X11 directory if it doesn't exist\n\
mkdir -p /tmp/.X11-unix\n\
chmod 1777 /tmp/.X11-unix\n\
echo "✅ X11 socket directory prepared"\n\
\n\
# Kill any existing Chrome processes\n\
pkill -9 chrome || true\n\
echo "✅ Cleaned up any existing Chrome processes"\n\
\n\
# Clear Chrome cache and temp files\n\
rm -rf /tmp/chrome/* /tmp/.org.chromium.Chromium* /tmp/.com.google.Chrome* 2>/dev/null || true\n\
rm -rf /dev/shm/* 2>/dev/null || true\n\
echo "✅ Cleared Chrome cache"\n\
\n\
# Test data directory is writable\n\
TEST_FILE="$DATA_DIR/startup_test.txt"\n\
if touch "$TEST_FILE"; then\n\
    echo "$(date) - Container startup" > "$TEST_FILE"\n\
    echo "✅ Data directory is writable"\n\
    rm "$TEST_FILE"\n\
else\n\
    echo "❌ ERROR: Data directory is not writable!"\n\
    exit 1\n\
fi\n\
\n\
# Start virtual display with standard resolution\n\
echo "Starting Xvfb virtual display on $DISPLAY"\n\
Xvfb $DISPLAY -screen 0 1920x1080x24 -ac +extension GLX +render -noreset > /dev/null 2>&1 &\n\
XVFB_PID=$!\n\
\n\
# Verify Xvfb is running\n\
sleep 2\n\
if ! ps -p $XVFB_PID > /dev/null; then\n\
    echo "❌ ERROR: Xvfb failed to start!"\n\
    exit 1\n\
fi\n\
echo "✅ Xvfb started successfully (PID: $XVFB_PID)"\n\
\n\
# Test Chrome can launch in headless mode\n\
echo "Testing Chrome launch..."\n\
timeout 10s google-chrome --headless=new --disable-gpu --no-sandbox --disable-dev-shm-usage about:blank > /dev/null 2>&1 || echo "Warning: Chrome test may have timed out (expected)"\n\
echo "✅ Chrome test completed"\n\
\n\
# Start the Flask application with gunicorn\n\
echo "Starting Flask application with Gunicorn"\n\
exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 180 "run:app"\n\
' > /app/startup.sh \
    && chmod +x /app/startup.sh

# Command to run
CMD ["/app/startup.sh"] 