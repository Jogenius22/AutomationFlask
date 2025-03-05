import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Base directory of the application
basedir = os.path.abspath(os.path.dirname(__file__))

# Path to data directory - Use environment variable or default location
# When running on GCP, we should use a path that's mounted as a persistent volume
# The persistent data path should be /app/data for consistency
PERSISTENT_DATA_DIR = '/app/data'  # This should be mounted as a persistent volume in GCP
LOCAL_DATA_DIR = os.path.join(basedir, 'data')

# Use the persistent directory if it exists and is writable
if os.path.exists(PERSISTENT_DATA_DIR) and os.access(PERSISTENT_DATA_DIR, os.W_OK):
    DATA_DIR = PERSISTENT_DATA_DIR
    print(f"Using persistent data directory: {DATA_DIR}")
else:
    # Fall back to local directory for development
    DATA_DIR = LOCAL_DATA_DIR
    print(f"Using local data directory: {DATA_DIR}")

# Create data directory structure with all necessary subdirectories
try:
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"Ensured data directory exists: {DATA_DIR}")
    
    # Create necessary subdirectories
    SCREENSHOTS_SUBDIR = os.path.join(DATA_DIR, 'screenshots')
    LOGS_SUBDIR = os.path.join(DATA_DIR, 'logs')
    
    os.makedirs(SCREENSHOTS_SUBDIR, exist_ok=True)
    os.makedirs(LOGS_SUBDIR, exist_ok=True)
    print(f"Created subdirectories: screenshots, logs")
    
    # Test write permissions by creating a small test file
    test_file = os.path.join(DATA_DIR, 'test_write.txt')
    with open(test_file, 'w') as f:
        f.write('Test write access')
    if os.path.exists(test_file):
        os.remove(test_file)
        print(f"Verified write access to {DATA_DIR}")
    else:
        print(f"WARNING: Could not verify write access to {DATA_DIR}")
        
except Exception as e:
    print(f"ERROR setting up data directory {DATA_DIR}: {str(e)}")
    # Emergency fallback - use current working directory
    DATA_DIR = os.path.join(os.getcwd(), 'data')
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"Using emergency fallback data directory: {DATA_DIR}")

# Define screenshots directory
SCREENSHOTS_DIR = os.path.join(DATA_DIR, 'screenshots')

# Data file paths
ACCOUNTS_FILE = os.path.join(DATA_DIR, 'accounts.json')
CITIES_FILE = os.path.join(DATA_DIR, 'cities.json')
MESSAGES_FILE = os.path.join(DATA_DIR, 'messages.json')
SCHEDULES_FILE = os.path.join(DATA_DIR, 'schedules.json')
LOGS_FILE = os.path.join(DATA_DIR, 'logs.json')
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')

print(f"Data files will be stored at:\n" +
      f"- Accounts: {ACCOUNTS_FILE}\n" +
      f"- Cities: {CITIES_FILE}\n" +
      f"- Messages: {MESSAGES_FILE}\n" +
      f"- Logs: {LOGS_FILE}")

# Initialize data files if they don't exist
def init_data_files():
    files = {
        ACCOUNTS_FILE: [],
        CITIES_FILE: [],
        MESSAGES_FILE: [],
        SCHEDULES_FILE: [],
        LOGS_FILE: [],
        SETTINGS_FILE: {
            "run_interval": 30,
            "max_posts_per_day": 10,
            "timeout_between_actions": 5,
            "enable_random_delays": True
        }
    }
    
    for file_path, default_data in files.items():
        if not os.path.exists(file_path):
            try:
                print(f"Creating data file: {os.path.basename(file_path)}")
                with open(file_path, 'w') as f:
                    json.dump(default_data, f, indent=4)
            except Exception as e:
                print(f"WARNING: Could not initialize data file {file_path}: {e}")
        else:
            print(f"Data file exists: {os.path.basename(file_path)}")
            # Check if file is valid JSON
            try:
                with open(file_path, 'r') as f:
                    json.load(f)
            except json.JSONDecodeError:
                print(f"WARNING: Data file {file_path} contains invalid JSON. Re-initializing.")
                with open(file_path, 'w') as f:
                    json.dump(default_data, f, indent=4)

# Initialize data files
try:
    init_data_files()
except Exception as e:
    print(f"WARNING: Could not initialize data files: {e}")

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    UPLOAD_FOLDER = os.path.join(DATA_DIR, 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    CAPSOLVER_API_KEY = os.environ.get('CAPSOLVER_API_KEY') or 'CAP-F79C6D0E7A810348A201783E25287C6003CFB45BBDCB670F96E525E7C0132148'
    SCREENSHOTS_DIR = SCREENSHOTS_DIR
    DATA_DIR = DATA_DIR
    
    @staticmethod
    def init_app(app):
        # Create uploads directory if it doesn't exist
        try:
            os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
            print(f"Created uploads directory: {Config.UPLOAD_FOLDER}")
        except Exception as e:
            print(f"WARNING: Could not create uploads directory: {e}")
            # Fallback to a directory in the data directory
            Config.UPLOAD_FOLDER = os.path.join(DATA_DIR, 'uploads')
            os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
            print(f"Using fallback uploads directory: {Config.UPLOAD_FOLDER}")

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
} 