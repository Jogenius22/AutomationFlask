"""
Debug script to help diagnose WSGI application issues
Run this manually on GCP to see what might be happening
"""
import os
import sys
import traceback

print("=" * 50)
print("WSGI Debug Information")
print("=" * 50)

print("\nPython version:", sys.version)
print("\nEnvironment Variables:")
for key, value in os.environ.items():
    print(f"{key}={value}")

print("\nCurrent Directory:", os.getcwd())
print("\nDirectory Contents:")
for root, dirs, files in os.walk('.', topdown=True):
    level = root.count(os.sep)
    indent = ' ' * 4 * level
    print(f"{indent}{os.path.basename(root)}/")
    sub_indent = ' ' * 4 * (level + 1)
    for file in files:
        print(f"{sub_indent}{file}")

print("\nPython Path:")
for path in sys.path:
    print(path)

print("\nTrying to import Flask and app...")
try:
    import flask
    print(f"Flask version: {flask.__version__}")
except Exception as e:
    print(f"Error importing Flask: {e}")
    traceback.print_exc()

try:
    from app import create_app
    print("Successfully imported create_app from app")
    
    app = create_app()
    print("Successfully created app instance")
    
    print("App routes:")
    for rule in app.url_map.iter_rules():
        print(f"{rule.endpoint}: {rule}")
except Exception as e:
    print(f"Error creating app: {e}")
    traceback.print_exc()

print("\nTrying to import wsgi...")
try:
    import wsgi
    print("Successfully imported wsgi")
    print("wsgi.app exists:", hasattr(wsgi, 'app'))
    print("wsgi.application exists:", hasattr(wsgi, 'application'))
except Exception as e:
    print(f"Error importing wsgi: {e}")
    traceback.print_exc()

print("=" * 50)
print("End of Debug Information")
print("=" * 50) 