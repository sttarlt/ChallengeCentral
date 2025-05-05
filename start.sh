#!/bin/bash

echo "=== Running pytest tests ==="
# Run tests and capture exit code (removing set -e to properly handle exit code)
python -m pytest -v
TEST_EXIT_CODE=$?

# Check if tests passed
if [ $TEST_EXIT_CODE -eq 0 ]; then
  echo "=== Tests passed successfully! ==="
  echo "=== Starting Flask application ==="
  
  # Start the Flask application
  exec gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app
else
  echo "=== Tests failed with exit code $TEST_EXIT_CODE! ==="
  echo "=== Please fix the test issues before running the application ==="
  exit 1
fi