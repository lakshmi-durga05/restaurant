# 🍽️ Restaurant GenAI Assistant

A powerful command-line based AI assistant for restaurant bookings, powered by local LLMs and RAG (Retrieval-Augmented Generation).

## 🚀 Features

### 🤖 Core AI Capabilities
- **Local LLM Integration**: Powered by Ollama for privacy-focused AI processing
- **Natural Language Understanding**: Book tables using conversational language
- **Context-Aware Responses**: Maintains conversation context for better interactions

### 🧠 Knowledge & RAG
- **Vector Database**: FAISS for efficient similarity search
- **Document Retrieval**: Retrieve relevant information from knowledge base
- **Custom Knowledge**: Easily extend the knowledge base with your own documents

### 📝 Booking Management
- **Smart Parsing**: Extract booking details from natural language
- **Flexible Input**: Accepts various date/time formats and natural language requests
- **Validation**: Ensures booking details are complete and valid
- **Beautiful UI**: Modern, elegant design with Tailwind CSS

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- [Ollama](https://ollama.ai/) installed and running
- Git (for cloning the repository)

### 1. Install Dependencies

First, clone the repository and install the required packages:

```bash
git clone https://github.com/yourusername/restaurant-genai.git
cd restaurant-genai
pip install -r requirements.txt
```

### 2. Set Up Ollama

Make sure you have Ollama installed and have downloaded the desired model:

```bash
ollama pull llama2  # or any other model you prefer
```

### 3. Initialize the Knowledge Base

```bash
python -c "from app.services.rag_service import RAGService; RAGService()"
```

### 4. Run the Application

Start the interactive CLI:

```bash
python cli.py
```

## 🎯 Usage Examples

### Make a Reservation
```
You: I'd like to book a table for 2 people tomorrow at 7pm

🤖 I found these booking details:
   • Name: Not specified
   • Party Size: 2
   • Date: 2023-09-07
   • Time: 19:00
   • Special Requests: None

✅ Your table has been reserved! We'll send a confirmation shortly.
```

### Ask Questions
```
You: What are your opening hours?

🤖 We're open from 11:00 AM to 10:00 PM from Monday to Saturday, and from 12:00 PM to 9:00 PM on Sundays. We are closed on major holidays.
```

## 🛠️ Extending the Knowledge Base

Add your own documents to the `data/knowledge_base` directory as JSON files with the following format:

```json
{
    "title": "Your Document Title",
    "content": "The content of your document..."
}
```

The system will automatically index new documents on the next startup.

## 🤖 Customizing the AI Model

You can change the default model by modifying the `AIService` initialization in `app/services/ai_service.py`:

```python
def __init__(self, model_name: str = "llama2"):
    self.llm = Ollama(model=model_name, temperature=0.7)
    # ... rest of the code
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
```bash
pip install -r requirements.txt
```

### 2. Set Up Database
Create a PostgreSQL database and update the connection string in `config.env`:
```env
DATABASE_URL=postgresql://username:password@localhost:5432/restaurant_booking
```

### 3. Install Ollama
```bash
# macOS/Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows
# Download from https://ollama.ai/download

# Pull the model
ollama pull llama2
```

### 4. Run the Application
```bash
python main.py
```

The application will be available at `http://localhost:8000`

## 🏗️ Architecture

### Backend Components
- **FastAPI**: Modern, fast web framework
- **SQLAlchemy**: Database ORM with PostgreSQL
- **RAG System**: FAISS vector search + Ollama LLM
- **NLP Service**: Natural language reservation parsing
- **Reservation Service**: Smart table allocation logic

### Database Schema
- **RestaurantSection**: Lake View, Garden View, Normal
- **Table**: Tables with capacities 2, 4, 6, 8, 12
- **Reservation**: Customer booking information

### AI Features
- **Semantic Search**: FAISS for finding relevant FAQ answers
- **Language Model**: Ollama for natural response generation
- **Text Processing**: spaCy for advanced NLP capabilities

## 📱 Usage Examples

### Natural Language Reservations
```
"I need a table for 4 people at 7 PM tomorrow in the garden view"
"Can I book for 6 people at 8:30 tonight?"
"Table for 2 at 6 PM in the lake view section"
```

### FAQ Questions
```
"What are your opening hours?"
"Do you have vegetarian options?"
"What's your cancellation policy?"
"Can I bring my own wine?"
```

## 🔧 Configuration

### Environment Variables
- `DATABASE_URL`: PostgreSQL connection string
- `OLLAMA_BASE_URL`: Ollama server URL (default: http://localhost:11434)
- `OLLAMA_MODEL`: Language model to use (default: llama2)

### Restaurant Settings
- **Hours**: 11:00 AM - 11:00 PM
- **Kitchen**: Closes at 10:30 PM
- **Sections**: Lake View, Garden View, Indoor
- **Table Sizes**: 2, 4, 6, 8, 12 seats

## 🧪 Testing

### Manual Testing
1. Start the application
2. Visit `http://localhost:8000`
3. Try natural language reservations
4. Test FAQ system
5. Use traditional reservation form

### API Testing
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## 🚀 Deployment

### Production Setup
1. Set up PostgreSQL database
2. Configure environment variables
3. Install production dependencies
4. Use production WSGI server (Gunicorn)
5. Set up reverse proxy (Nginx)

### Docker (Coming Soon)
```bash
docker build -t restaurant-booking .
docker run -p 8000:8000 restaurant-booking
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Documentation**: Check the API docs at `/docs`
- **Issues**: Report bugs via GitHub Issues
- **Email**: info@lakeviewgardens.com

## 🎯 Roadmap

- [ ] Mobile app
- [ ] SMS notifications
- [ ] Payment integration
- [ ] Analytics dashboard
- [ ] Multi-language support
- [ ] Advanced AI features

---

**Built with ❤️ for the perfect dining experience**
