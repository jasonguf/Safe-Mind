#!/bin/bash
# Build script for macOS

echo "==================================="
echo "NeuroView macOS Build Script"
echo "==================================="

# Check if we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "Error: This script is for macOS only"
    exit 1
fi

# Navigate to project directory
cd "$(dirname "$0")"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/upgrade dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build dist

# Build the app
echo "Building NeuroView.app..."
pyinstaller neuroview.spec --clean

# Check if build was successful
if [ -d "dist/NeuroView.app" ]; then
    echo ""
    echo "==================================="
    echo "Build successful!"
    echo "==================================="
    echo "App location: dist/NeuroView.app"
    echo ""
    echo "To run: open dist/NeuroView.app"
    echo "To distribute: zip the NeuroView.app folder"
else
    echo ""
    echo "Build failed. Check the output above for errors."
    exit 1
fi

# Deactivate virtual environment
deactivate
