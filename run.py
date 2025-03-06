from app import create_app
import os

# Create the Flask application
app = create_app()

# This is used when running the app locally
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5001)), debug=False) 