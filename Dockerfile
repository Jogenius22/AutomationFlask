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
    procps \
    psmisc \
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

# Create persistent data directory structure with correct permissions
# This directory will be mounted as a volume in production
RUN mkdir -p /app/data/screenshots /app/data/logs /app/data/uploads \
    && chmod -R 777 /app/data \
    && ls -la /app/data

# Create directories needed for Chrome and Xvfb
RUN mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix \
    && mkdir -p /tmp/chrome && chmod 777 /tmp/chrome \
    && mkdir -p /dev/shm && chmod 777 /dev/shm

# Set environment variables
ENV FLASK_APP=app
ENV FLASK_DEBUG=0
ENV DISPLAY=:99
ENV PYTHONUNBUFFERED=1
ENV SELENIUM_HEADLESS=true
ENV PYTHONPATH=/app
# Chrome flags for better extension support in headless mode
ENV CHROME_ARGS="--no-sandbox --disable-dev-shm-usage --disable-gpu --disable-web-security --allow-running-insecure-content --window-size=1280,800 --remote-debugging-port=9222 --memory-pressure-off --disable-extensions"
# Ensure proper paths
ENV DATA_DIR=/app/data
# Only show automation logs, not initialization logs
ENV LOG_LEVEL_FILTER=automation
# Set HOME directory for Chrome
ENV HOME=/tmp/chrome
# Use a lower memory ceiling for Chrome to prevent OOM issues
ENV PYTHONIOENCODING=utf-8
ENV MALLOC_TRIM_THRESHOLD_=100000
ENV MALLOC_ARENA_MAX=2

# Create startup script with improved error handling and data directory checks
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Print environment for debugging\n\
echo "Starting container with:"\n\
echo "- Data directory: $DATA_DIR"\n\
echo "- Display: $DISPLAY"\n\
echo "- Chrome args: $CHROME_ARGS"\n\
echo "- Log filter: $LOG_LEVEL_FILTER"\n\
\n\
# Enable memory trimming\n\
echo 1 > /proc/sys/vm/overcommit_memory || echo "Warning: Could not set overcommit_memory (expected in some environments)"\n\
\n\
# Ensure data directories exist and have correct permissions\n\
mkdir -p "$DATA_DIR/screenshots" "$DATA_DIR/logs" "$DATA_DIR/uploads"\n\
chmod -R 777 "$DATA_DIR"\n\
ls -la "$DATA_DIR"\n\
echo "✅ Data directory structure verified"\n\
\n\
# Make sure data files are initialized\n\
python -c "from config import init_data_files; init_data_files()"\n\
\n\
# Aggressively clean up any existing Chrome processes\n\
echo "Cleaning up any existing Chrome processes..."\n\
pkill -9 chrome || true\n\
pkill -9 Xvfb || true\n\
killall -9 chrome || true\n\
killall -9 chromedriver || true\n\
echo "✅ Process cleanup completed"\n\
\n\
# Clear all Chrome cache directories\n\
echo "Clearing Chrome cache directories..."\n\
rm -rf /tmp/chrome/* /tmp/.org.chromium.Chromium* /tmp/.com.google.Chrome* 2>/dev/null || true\n\
rm -rf /dev/shm/* 2>/dev/null || true\n\
# Recreate the directories with proper permissions\n\
mkdir -p /tmp/chrome\n\
chmod -R 777 /tmp/chrome\n\
mkdir -p /tmp/.X11-unix\n\
chmod 1777 /tmp/.X11-unix\n\
echo "✅ Chrome directories prepared"\n\
\n\
# Test data directory is writable\n\
TEST_FILE="$DATA_DIR/startup_test.txt"\n\
if touch "$TEST_FILE"; then\n\
    echo "$(date) - Container startup" > "$TEST_FILE"\n\
    echo "✅ Data directory is writable"\n\
    ls -la "$DATA_DIR"\n\
    echo "Data directory contents:"\n\
    find "$DATA_DIR" -type f | xargs ls -la 2>/dev/null || echo "No files found"\n\
    # Check if data files exist and are valid JSON\n\
    echo "Validating data files..."\n\
    python -c "import json, os; print(f\\"accounts.json valid: {os.path.exists(\\"$DATA_DIR/accounts.json\\") and len(json.load(open(\\"$DATA_DIR/accounts.json\\"))) >= 0 if os.path.exists(\\"$DATA_DIR/accounts.json\\") else False}\\")" || echo "Could not validate accounts.json"\n\
    python -c "import json, os; print(f\\"cities.json valid: {os.path.exists(\\"$DATA_DIR/cities.json\\") and len(json.load(open(\\"$DATA_DIR/cities.json\\"))) >= 0 if os.path.exists(\\"$DATA_DIR/cities.json\\") else False}\\")" || echo "Could not validate cities.json"\n\
    python -c "import json, os; print(f\\"messages.json valid: {os.path.exists(\\"$DATA_DIR/messages.json\\") and len(json.load(open(\\"$DATA_DIR/messages.json\\"))) >= 0 if os.path.exists(\\"$DATA_DIR/messages.json\\") else False}\\")" || echo "Could not validate messages.json"\n\
    rm "$TEST_FILE"\n\
else\n\
    echo "❌ ERROR: Data directory is not writable!"\n\
    exit 1\n\
fi\n\
\n\
# Start virtual display with standard resolution\n\
echo "Starting Xvfb virtual display on $DISPLAY"\n\
Xvfb $DISPLAY -screen 0 1280x800x24 -ac +extension GLX +render -noreset > /dev/null 2>&1 &\n\
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
# Test Chrome can launch in headless mode with lower timeout\n\
echo "Testing Chrome launch..."\n\
timeout 5s google-chrome --headless=new --disable-gpu --no-sandbox --disable-dev-shm-usage about:blank > /dev/null 2>&1 || echo "Chrome test completed with timeout (expected)"\n\
echo "✅ Chrome test completed"\n\
\n\
# Print memory information\n\
echo "Memory information:"\n\
free -m || echo "free command not available"\n\
\n\
# Start the Flask application with gunicorn with optimized worker settings\n\
echo "Starting Flask application with Gunicorn"\n\
exec gunicorn -c /app/gunicorn.conf.py\n\
' > /app/startup.sh \
    && chmod +x /app/startup.sh

# Command to run
CMD ["/app/startup.sh"] 