#!/bin/bash

# Activate the virtual environment
echo "Activating virtual environment..."
source "$(dirname "$0")/venv/bin/activate"

# Run Flask app
echo "Running Flask app..."
python app.py
