#!/bin/bash

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi

# Activate the virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install required packages
echo "Installing requirements..."
pip install -r requirements.txt

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Auto-exit
exit 0
