#!/usr/bin/python3
import sys
import os

# Add the application directory to the Python path
sys.path.insert(0, '/var/www/visualizacion-estudiantes')

# Set the FLASK_APP environment variable
os.environ['FLASK_APP'] = 'run.py'

# Import the Flask application
from run import app as application

if __name__ == '__main__':
    application.run()