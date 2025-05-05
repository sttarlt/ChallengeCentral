#!/bin/bash

# Set strict error handling
set -e

echo "Running tests..."
# Run pytest tests
python -m pytest

# Check if tests passed
if [ $? -eq 0 ]; then
  echo "Tests passed successfully! Starting Flask application..."
  
  # Start the Flask application
  exec gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app
else
  echo "Tests failed! Fix the issues before running the application."
  exit 1
fi