#!/bin/bash

if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing requirements..."
pip install -r requirements.txt

echo "Upgrading pip..."
pip install --upgrade pip

echo "Running Flask app..."
python app.py
