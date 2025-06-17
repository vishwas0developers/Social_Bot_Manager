#!/bin/bash

# Create venv if not exists
if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi

# Activate venv
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing requirements..."
pip install -r requirements.txt

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

read -p "Press any key to continue..."
