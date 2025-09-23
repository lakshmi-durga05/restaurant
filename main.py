import uvicorn
from app.main import app

if __name__ == "__main__":
    print("🚀 Starting Restaurant GenAI Assistant...")
    
    # Start the server
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
