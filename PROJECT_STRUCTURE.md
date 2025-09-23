# 🏗️ Project Structure

```
restaurant_booking/
├── 📁 app/                          # Main application package
│   ├── __init__.py                  # Package initialization
│   ├── main.py                      # FastAPI application and routes
│   ├── models.py                    # SQLAlchemy database models
│   ├── schemas.py                   # Pydantic data validation schemas
│   ├── database.py                  # Database connection and session management
│   ├── reservation_service.py       # Business logic for reservations
│   ├── rag_system.py               # RAG system for FAQ handling
│   ├── nlp_service.py              # Natural language processing
│   ├── init_db.py                  # Database initialization script
│   └── 📁 templates/               # HTML templates
│       ├── base.html               # Base template with navigation
│       └── index.html              # Main page with reservation interface
├── 📄 main.py                       # Application entry point
├── 📄 setup.py                      # Setup and installation script
├── 📄 demo.py                       # Demo script to test the system
├── 📄 start.bat                     # Windows batch file to start the app
├── 📄 requirements.txt              # Python dependencies
├── 📄 config.env                    # Environment configuration
├── 📄 README.md                     # Comprehensive project documentation
└── 📄 PROJECT_STRUCTURE.md          # This file
```

## 🔧 Core Components

### 1. **FastAPI Application** (`app/main.py`)
- REST API endpoints for reservations and FAQs
- Natural language reservation processing
- Web interface serving

### 2. **Database Layer** (`app/models.py`, `app/database.py`)
- SQLAlchemy ORM models for restaurant data
- Database connection management
- Support for both PostgreSQL and SQLite

### 3. **Reservation Service** (`app/reservation_service.py`)
- Intelligent table allocation
- Alternative table suggestions
- Availability checking

### 4. **AI FAQ System** (`app/rag_system.py`)
- FAISS vector search for semantic similarity
- Ollama integration for natural language generation
- Pre-built knowledge base

### 5. **NLP Service** (`app/nlp_service.py`)
- Natural language reservation parsing
- Date, time, and party size extraction
- Section preference detection

### 6. **Web Interface** (`app/templates/`)
- Modern, responsive design with Tailwind CSS
- Natural language input interface
- Traditional reservation form
- Interactive FAQ chat system

## 🚀 Getting Started

### Quick Start (Windows)
```bash
# Double-click start.bat or run:
start.bat
```

### Quick Start (All Platforms)
```bash
# Install dependencies
python setup.py

# Start the application
python main.py
```

### Manual Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configure database in config.env
# Start the application
python main.py
```

## 🌐 Access Points

- **Main Interface**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/api/health

## 🔍 Key Features Demonstrated

### Natural Language Reservations
```
"I need a table for 4 people at 7 PM tomorrow in the garden view"
"Can I book for 6 people at 8:30 tonight?"
"Table for 2 at 6 PM in the lake view section"
```

### AI-Powered FAQ
- Semantic search for relevant answers
- Natural, conversational responses
- Comprehensive restaurant knowledge

### Smart Table Allocation
- Automatic capacity matching
- Section preference handling
- Alternative suggestions when exact matches aren't available

## 🧪 Testing

### Run Demo
```bash
python demo.py
```

### Manual Testing
1. Start the application
2. Visit the web interface
3. Try natural language reservations
4. Test the FAQ system
5. Use the traditional form

## 🔧 Configuration

### Environment Variables (`config.env`)
- `DATABASE_URL`: Database connection string
- `OLLAMA_BASE_URL`: Ollama server URL
- `OLLAMA_MODEL`: Language model name

### Database Options
- **SQLite** (default for development): `sqlite:///./restaurant_booking.db`
- **PostgreSQL**: `postgresql://user:pass@localhost:5432/dbname`

## 📚 API Endpoints

### Reservations
- `POST /api/reservations` - Create reservation
- `POST /api/reservations/natural` - Natural language reservation
- `DELETE /api/reservations/{id}` - Cancel reservation

### Information
- `GET /api/sections` - Restaurant sections
- `GET /api/tables` - Available tables
- `GET /api/available-times` - Available reservation times

### AI Features
- `POST /api/faq` - Ask FAQ questions

## 🎯 Next Steps

1. **Customize**: Modify restaurant details in `app/init_db.py`
2. **Extend**: Add new FAQ categories in `app/rag_system.py`
3. **Deploy**: Set up production database and server
4. **Enhance**: Add SMS notifications, payment integration, etc.

---

**The system is ready to use! Start with `python main.py` and enjoy your AI-powered restaurant reservation manager! 🎉**
