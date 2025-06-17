#!/bin/bash

# Install required packages from requirements.txt
echo "Installing required packages..."
pip install -r requirements.txt

# Upgrade pip to the latest version
echo "Upgrading pip..."
pip install --upgrade pip

read -p "Press any key to continue..."
