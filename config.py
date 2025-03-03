import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Base directory of the application
basedir = os.path.abspath(os.path.dirname(__file__))

# Path to data directory - Use environment variable or default location
# Allow Render to use the mounted volume at /app/data if available
DATA_DIR = os.environ.get('DATA_DIR') or os.path.join(basedir, 'data')

# Create data directory if it doesn't exist
if not os.path.exists(DATA_DIR):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not create data directory: {e}")
        # Fallback - use a directory in the current working directory
        DATA_DIR = os.path.join(os.getcwd(), 'data')
        os.makedirs(DATA_DIR, exist_ok=True)

# Define screenshots directory 
SCREENSHOTS_DIR = os.environ.get('SCREENSHOTS_DIR') or os.path.join(DATA_DIR, 'screenshots')
try:
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
except Exception as e:
    print(f"Warning: Could not create screenshots directory: {e}")
    # Fallback - use a directory in the current working directory
    SCREENSHOTS_DIR = os.path.join(os.getcwd(), 'screenshots')
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# Data file paths
ACCOUNTS_FILE = os.path.join(DATA_DIR, 'accounts.json')
CITIES_FILE = os.path.join(DATA_DIR, 'cities.json')
MESSAGES_FILE = os.path.join(DATA_DIR, 'messages.json')
SCHEDULES_FILE = os.path.join(DATA_DIR, 'schedules.json')
LOGS_FILE = os.path.join(DATA_DIR, 'logs.json')
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')

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
                with open(file_path, 'w') as f:
                    json.dump(default_data, f, indent=4)
            except Exception as e:
                print(f"Warning: Could not initialize data file {file_path}: {e}")

# Initialize data files
try:
    init_data_files()
except Exception as e:
    print(f"Warning: Could not initialize data files: {e}")

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    UPLOAD_FOLDER = os.path.join(basedir, 'app/static/uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    CAPSOLVER_API_KEY = os.environ.get('CAPSOLVER_API_KEY') or 'CAP-F79C6D0E7A810348A201783E25287C6003CFB45BBDCB670F96E525E7C0132148'
    SCREENSHOTS_DIR = SCREENSHOTS_DIR
    
    @staticmethod
    def init_app(app):
        # Create uploads directory if it doesn't exist
        try:
            os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        except Exception as e:
            print(f"Warning: Could not create uploads directory: {e}")
            # Fallback to a directory in the current working directory
            Config.UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
            os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

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