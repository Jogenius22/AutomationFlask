# Automation Flask

A Flask-based web application for managing and running Selenium automation tasks, specifically designed for Airtasker automation.

## Features

- Web interface for managing automation accounts, cities, and messages
- Scheduling system for automated tasks
- Selenium-based automation with Capsolver integration for CAPTCHA solving
- Comprehensive testing framework

## Installation

1. Clone the repository:

```bash
git clone https://github.com/Jogenius22/AutomationFlask.git
cd AutomationFlask
```

2. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Set up environment variables (optional):

```bash
export FLASK_APP=wsgi.py
export FLASK_ENV=development
export CAPSOLVER_API_KEY=your_api_key_here  # Optional, default key is provided
```

## Running the Application

### Development Mode

```bash
python -m flask run
```

### Production Mode with Gunicorn

```bash
gunicorn wsgi:app
```

## Testing the Automation

The project includes a comprehensive testing framework to verify the automation functionality:

```bash
python test_automation.py
```

This will run tests for:

- Driver initialization
- Capsolver extension loading
- Airtasker login page access
- Full automation flow (without submitting credentials)

## Project Structure

- `app/` - Main application code
  - `automations/` - Selenium automation scripts
    - `main.py` - Core automation functionality
    - `comments.py` - Comment posting functionality
  - `templates/` - Flask HTML templates
  - `static/` - CSS, JavaScript, and other static files
  - `routes.py` - Flask routes
  - `data_manager.py` - Data management utilities
- `data/` - Data storage directory
  - `logs/` - Log files
  - `screenshots/` - Automation screenshots
- `test_automation.py` - Automation testing script

## Automation Features

The automation system includes:

1. **Robust WebDriver Initialization**:

   - Automatic ChromeDriver installation
   - Headless mode support
   - Cleanup of stray Chrome processes

2. **Captcha Solving**:

   - Integration with Capsolver extension
   - Automatic handling of reCAPTCHA challenges

3. **Login Functionality**:

   - Secure credential handling
   - Detailed logging and error handling

4. **Task Interaction**:
   - Commenting on tasks
   - Location-based filtering

## Troubleshooting

### Chrome Process Issues

If you encounter issues with Chrome processes not closing properly:

```bash
# On macOS/Linux
pkill -f chrome

# On Windows
taskkill /F /IM chrome.exe
```

### Log Files

Check the log files in the `data/logs` directory for detailed error information.

## License

This project is proprietary and confidential. Unauthorized copying, distribution, or use is strictly prohibited.
