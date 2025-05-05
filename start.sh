#!/bin/bash

# Setup log timestamp for this run
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
LOG_DIR="test_logs"
REPORT_DIR="test_reports"

# Ensure directories exist
mkdir -p "$LOG_DIR" "$REPORT_DIR"

# Mark explicitly as Replit environment (even if REPL_ID is not set)
export REPLIT_ENVIRONMENT=true

# Setup environment for testing
export FLASK_ENV=testing
export TEST_DATABASE_URL=sqlite:///test.db

run_tests() {
  local test_type=$1
  local test_path="tests"
  local test_description="all"
  
  # Determine test path based on type
  if [ "$test_type" == "unit" ]; then
    test_path="tests/unit"
    test_description="unit"
  elif [ "$test_type" == "integration" ]; then
    test_path="tests/integration"
    test_description="integration"
  fi
  
  echo "=== Running $test_description tests ==="
  
  # Run tests with HTML report and log capture
  python -m pytest "$test_path" -v \
    --html="$REPORT_DIR/${TIMESTAMP}_${test_description}_report.html" \
    2>&1 | tee "$LOG_DIR/${TIMESTAMP}_${test_description}_test.log"
  
  # Capture exit code using PIPESTATUS to account for tee pipe
  return ${PIPESTATUS[0]}
}

# Process command line arguments for test types
if [ "$1" == "unit" ]; then
  run_tests "unit"
  TEST_EXIT_CODE=$?
elif [ "$1" == "integration" ]; then
  run_tests "integration"
  TEST_EXIT_CODE=$?
else
  run_tests "all"
  TEST_EXIT_CODE=$?
fi

# Check if tests passed
if [ $TEST_EXIT_CODE -eq 0 ]; then
  echo "=== Tests passed successfully! ==="
  echo "=== HTML report available at: $REPORT_DIR/${TIMESTAMP}_*_report.html ==="
  echo "=== Test logs available at: $LOG_DIR/${TIMESTAMP}_*_test.log ==="
  echo ""
  echo "=== Starting Flask application ==="
  
  # Reset environment variables for production
  unset FLASK_ENV
  unset TEST_DATABASE_URL
  
  # Start the Flask application
  exec gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app
else
  echo "=== Tests failed with exit code $TEST_EXIT_CODE! ==="
  echo "=== HTML report available at: $REPORT_DIR/${TIMESTAMP}_*_report.html ==="
  echo "=== Test logs available at: $LOG_DIR/${TIMESTAMP}_*_test.log ==="
  echo "=== Please fix the test issues before running the application ==="
  exit 1
fi