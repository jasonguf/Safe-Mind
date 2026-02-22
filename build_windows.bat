@echo off
REM Build script for Windows

echo ===================================
echo NeuroView Windows Build Script
echo ===================================

REM Navigate to project directory
cd /d "%~dp0"

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install/upgrade dependencies
echo Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt

REM Clean previous builds
echo Cleaning previous builds...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

REM Build the executable
echo Building NeuroView.exe...
pyinstaller neuroview.spec --clean

REM Check if build was successful
if exist "dist\NeuroView\NeuroView.exe" (
    echo.
    echo ===================================
    echo Build successful!
    echo ===================================
    echo Executable location: dist\NeuroView\NeuroView.exe
    echo.
    echo To run: double-click dist\NeuroView\NeuroView.exe
    echo To distribute: zip the entire dist\NeuroView folder
) else (
    echo.
    echo Build failed. Check the output above for errors.
    exit /b 1
)

REM Deactivate virtual environment
deactivate

pause
