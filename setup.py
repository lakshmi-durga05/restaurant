#!/usr/bin/env python3
"""
Setup script for Lakeview Gardens Restaurant Reservation Manager
"""

import os
import sys
import subprocess
import sqlite3
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ is required")
        sys.exit(1)
    print("✅ Python version check passed")

def install_dependencies():
    """Install required Python packages"""
    print("📦 Installing Python dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully")
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        sys.exit(1)

def create_sqlite_database():
    """Create SQLite database for development/testing"""
    print("🗄️ Creating SQLite database for development...")
    
    # Update config to use SQLite
    config_content = """# Database Configuration (SQLite for development)
DATABASE_URL=sqlite:///./restaurant_booking.db

# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2

# Restaurant Configuration
RESTAURANT_NAME=Lakeview Gardens
OPENING_TIME=11:00
CLOSING_TIME=23:00
"""
    
    with open("config.env", "w") as f:
        f.write(config_content)
    
    print("✅ SQLite database configured")

def check_ollama():
    """Check if Ollama is available"""
    print("🤖 Checking Ollama availability...")
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            print("✅ Ollama is running")
            return True
        else:
            print("⚠️ Ollama is not responding properly")
            return False
    except:
        print("⚠️ Ollama is not running or not accessible")
        print("   To install Ollama, visit: https://ollama.ai/download")
        print("   After installation, run: ollama pull llama2")
        return False

def create_directories():
    """Create necessary directories"""
    print("📁 Creating directories...")
    Path("app/templates").mkdir(parents=True, exist_ok=True)
    print("✅ Directories created")

def main():
    """Main setup function"""
    print("🏞️ Lakeview Gardens Restaurant Reservation Manager Setup")
    print("=" * 60)
    
    # Check Python version
    check_python_version()
    
    # Create directories
    create_directories()
    
    # Install dependencies
    install_dependencies()
    
    # Create SQLite database for development
    create_sqlite_database()
    
    # Check Ollama
    ollama_available = check_ollama()
    
    print("\n🎉 Setup completed!")
    print("\n📋 Next steps:")
    print("1. Start the application: python main.py")
    print("2. Open your browser to: http://localhost:8000")
    
    if not ollama_available:
        print("\n⚠️ Note: Ollama is not available, so AI features will be limited")
        print("   Install Ollama for full AI functionality")
    
    print("\n🚀 Happy dining!")

if __name__ == "__main__":
    main()
