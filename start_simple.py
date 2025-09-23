#!/usr/bin/env python3
"""
Simple startup script for Lakeview Gardens Restaurant Reservation Manager
"""

import sys
import os

def check_dependencies():
    """Check if basic dependencies are available"""
    try:
        import fastapi
        import uvicorn
        import sqlalchemy
        print("✅ Basic dependencies are available")
        return True
    except ImportError as e:
        print(f"❌ Missing basic dependency: {e}")
        return False

def install_simple_requirements():
    """Install simple requirements without heavy AI dependencies"""
    print("📦 Installing simple requirements...")
    try:
        os.system(f"{sys.executable} -m pip install -r requirements-simple.txt")
        print("✅ Simple requirements installed")
        return True
    except Exception as e:
        print(f"❌ Failed to install simple requirements: {e}")
        return False

def main():
    """Main startup function"""
    print("🏞️ Lakeview Gardens Restaurant Reservation Manager - Simple Mode")
    print("=" * 70)
    
    # Check if we're in the right directory
    if not os.path.exists("app"):
        print("❌ Please run this script from the restaurant_booking directory")
        return
    
    # Check basic dependencies
    if not check_dependencies():
        print("\n📦 Installing basic dependencies...")
        if not install_simple_requirements():
            print("❌ Failed to install dependencies. Please run: pip install -r requirements-simple.txt")
            return
    
    print("\n🚀 Starting the application in simple mode...")
    print("Note: AI features will use simplified algorithms")
    
    try:
        # Import and run the main application
        from app.main import app
        from app.init_db import init_database
        
        # Initialize database
        print("📊 Initializing database...")
        init_database()
        
        # Start the server
        print("🌐 Starting FastAPI server...")
        import uvicorn
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
        
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        print("\n🔧 Troubleshooting:")
        print("1. Make sure you're in the restaurant_booking directory")
        print("2. Try: pip install -r requirements-simple.txt")
        print("3. Check if Python 3.8+ is installed")

if __name__ == "__main__":
    main()
