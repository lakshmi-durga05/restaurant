# 🍽️ Lakeside Bistro Restaurant Booking System

A modern, AI-powered restaurant reservation system with intelligent table management and chatbot assistance.

## 🌟 Features

### 📋 Form-Based Booking System
- **Simple 3-step booking process**: Select section → Choose date/time → Enter details
- **Real-time availability checking** with live API integration
- **Priority-based suggestions** (Lake View → Garden View → Indoors)
- **Table combination logic** (2×2 seaters can combine for 4 people)

### 🏢 Restaurant Layout
Based on the provided floor plan with 4 distinct sections:

#### Lake View (Tables 10-15) - **Highest Priority**
- 2×2 seaters (Tables 14, 15)
- 2×4 seaters (Tables 12, 13) 
- 2×12 seaters (Tables 10, 11)

#### Garden View (Tables 16-21) - **Second Priority**
- 2×2 seaters (Tables 20, 21)
- 2×4 seaters (Tables 18, 19)
- 2×12 seaters (Tables 16, 17)

#### Indoors (Tables 1-9) - **Third Priority**
- 4×2 seaters (Tables 2, 3, 6, 7, 8, 9)
- 2×4 seaters (Tables 4, 5)
- 1×12 seater (Table 1)

#### Private Area (Table 22) - **Special Priority**
- 1×30 seater U-shaped table for large groups

### 🤖 AI-Powered Chatbot
- **RAG (Retrieval-Augmented Generation)** system using transformers and Ollama
- **Natural language processing** for restaurant queries
- **Knowledge base** with FAQ about hours, policies, menu, etc.
- **Real-time responses** with confidence scoring

### 🎯 Smart Table Management
- **Priority-based allocation**: Automatically suggests alternatives in priority order
- **Table combination**: Intelligently combines 2×2 seaters for 4-person parties
- **Availability tracking**: Real-time table availability checking
- **Alternative suggestions**: When preferred section is unavailable

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Ollama (for AI chatbot functionality)
- Required Python packages (see requirements.txt)

### Installation

1. **Clone and setup**:
```bash
git clone <repository>
cd restaurant_booking
pip install -r requirements.txt
```

2. **Start Ollama** (for chatbot):
```bash
# Install Ollama from https://ollama.ai
ollama serve
ollama pull llama2  # or your preferred model
```

3. **Run the system**:
```bash
python start_restaurant.py
```

4. **Access the application**:
- Main website: http://localhost:8000
- API documentation: http://localhost:8000/docs
- Booking form: http://localhost:8000/book

### Testing
```bash
python test_system.py
```

## 🏗️ System Architecture

### Backend (FastAPI)
- **`app/main.py`**: Main FastAPI application with endpoints
- **`app/models.py`**: Database models (RestaurantSection, Table, Reservation)
- **`app/schemas.py`**: Pydantic schemas for API validation
- **`app/reservation_service.py`**: Core booking logic with priority management
- **`app/rag_system.py`**: AI chatbot with RAG implementation
- **`app/init_db.py`**: Database initialization with restaurant layout

### Frontend (HTML/CSS/JavaScript)
- **`templates/index.html`**: Main restaurant website with chatbot
- **`templates/book.html`**: 3-step booking form
- **`templates/base.html`**: Base template with Bootstrap styling
- **`static/`**: CSS and JavaScript files

### Database (SQLite)
- **Restaurant sections** with priority ordering
- **Tables** with capacity and section mapping
- **Reservations** with customer details and status tracking

## 🔧 API Endpoints

### Booking
- `POST /api/reservations` - Create new reservation
- `GET /api/available-times` - Get available time slots
- `GET /api/sections` - Get restaurant sections
- `GET /api/tables` - Get tables (optionally filtered by section)

### Chatbot
- `POST /api/chatbot` - Ask questions to restaurant assistant
- `POST /api/faq` - FAQ endpoint (legacy)

### Admin
- `GET /api/admin/customers` - Get all customer data
- `GET /api/admin/reservations` - Get all reservations
- `DELETE /api/reservations/{id}` - Cancel reservation

## 🎨 User Interface

### Homepage
- **Hero section** with booking CTA and chatbot access
- **Restaurant information** with gallery and testimonials
- **Chatbot modal** for customer queries

### Booking Form
- **Step 1**: Select preferred seating section with visual cards
- **Step 2**: Choose date, party size, and available time slots
- **Step 3**: Enter customer details and special requests
- **Confirmation**: Success message with reservation details

### Responsive Design
- **Mobile-friendly** with Bootstrap responsive grid
- **Modern UI** with smooth animations and transitions
- **Accessible** with proper ARIA labels and keyboard navigation

## 🧠 AI Features

### RAG System Components
- **Sentence Transformers**: For embedding generation
- **FAISS**: For vector similarity search
- **Ollama**: For LLM inference
- **Knowledge Base**: Curated restaurant FAQ data

### Chatbot Capabilities
- **Restaurant hours and policies**
- **Menu and dietary information**
- **Reservation policies**
- **General restaurant queries**

## 📊 Database Schema

### RestaurantSection
- `id`, `name`, `description`
- `priority` (1=Lake View, 2=Garden View, 3=Indoors, 4=Private)
- `max_*_seaters` (capacity limits)
- `can_combine_tables` (boolean)

### Table
- `id`, `table_number`, `capacity`
- `section_id` (foreign key)
- `is_active`, `is_combined`

### Reservation
- `id`, `customer_name`, `customer_email`, `customer_phone`
- `party_size`, `reservation_date`, `reservation_time`
- `section_preference`, `table_id`
- `status` (confirmed, pending, cancelled)
- `special_requests`

## 🔄 Business Logic

### Priority System
1. **Lake View** (Priority 1) - Highest demand, best views
2. **Garden View** (Priority 2) - Popular outdoor seating
3. **Indoors** (Priority 3) - Reliable indoor option
4. **Private Area** (Priority 4) - Special large group area

### Table Combination
- **2×2 seaters** can be combined for 4-person parties
- **Automatic detection** when 4-seater tables unavailable
- **Priority-based** combination suggestions

### Availability Logic
- **Real-time checking** against existing reservations
- **Capacity validation** to prevent overbooking
- **Alternative suggestions** when preferred options unavailable

## 🛠️ Configuration

### Environment Variables
- `RAG_MODE`: "full", "simple", or "auto" (default)
- `OLLAMA_BASE_URL`: Ollama server URL (default: http://localhost:11434)
- `OLLAMA_MODEL`: Model name (default: llama2)

### Customization
- **Restaurant hours**: Modify in `reservation_service.py`
- **Table layout**: Update `init_db.py`
- **FAQ content**: Edit `rag_system.py`
- **UI styling**: Modify CSS in templates

## 🧪 Testing

The system includes comprehensive tests:
- **Database initialization** verification
- **Reservation logic** testing
- **RAG system** functionality
- **API endpoint** validation

Run tests with: `python test_system.py`

## 📝 Development Notes

### Code Structure
- **Simple and clean** - Easy to understand and maintain
- **Modular design** - Separate concerns (models, services, API)
- **Error handling** - Graceful fallbacks and user feedback
- **Documentation** - Comprehensive comments and docstrings

### Performance Considerations
- **Efficient queries** with proper indexing
- **Caching** for frequently accessed data
- **Async operations** where appropriate
- **Database connection pooling**

## 🚀 Deployment

### Production Setup
1. **Database**: Use PostgreSQL for production
2. **Web server**: Deploy with Gunicorn + Nginx
3. **AI services**: Ensure Ollama is running and accessible
4. **Environment**: Set production environment variables

### Docker Support
```dockerfile
# Example Dockerfile structure
FROM python:3.9-slim
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "start_restaurant.py"]
```

## 📞 Support

For questions or issues:
- Check the test suite: `python test_system.py`
- Review API documentation: http://localhost:8000/docs
- Examine the code structure and comments
- Test individual components separately

---

**Built for internship evaluation** - Demonstrating modern web development, AI integration, and restaurant management systems.

