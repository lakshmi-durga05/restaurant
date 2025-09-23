#!/usr/bin/env python3
"""
Restaurant Booking System Startup Script
This script initializes the database and starts the FastAPI application.
"""

import os
import sys
import uvicorn
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

def main():
    """Main startup function"""
    print("🍽️  Starting Lakeside Bistro Restaurant Booking System...")
    print("=" * 60)
    
    # Initialize database
    try:
        from app.init_db import init_database
        print("📊 Initializing database...")
        init_database()
        print("✅ Database initialized successfully!")
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        return
    
    # Start the application
    print("\n🚀 Starting web server...")
    print("📍 Application will be available at: http://localhost:8000")
    print("📖 API documentation at: http://localhost:8000/docs")
    print("🛑 Press Ctrl+C to stop the server")
    print("=" * 60)
    
    try:
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped. Goodbye!")
    except Exception as e:
        print(f"❌ Error starting server: {e}")

if __name__ == "__main__":
    main()

