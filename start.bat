@echo off
echo 🏞️ Starting Lakeview Gardens Restaurant Reservation Manager...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

REM Check if requirements are installed
echo 📦 Checking dependencies...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ Failed to install dependencies
        pause
        exit /b 1
    )
)

REM Start the application
echo 🚀 Starting the application...
echo.
echo The restaurant booking system will be available at:
echo 🌐 http://localhost:8000
echo 📚 API docs: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server
echo.

python main.py

pause
