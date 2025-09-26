# Restaurant Booking Assistant — Project Guide

## Overview
This project is a FastAPI-based restaurant booking assistant with natural-language chat, live seat-map visualization, booking/availability logic, and optional AI integrations (LangChain vector store, CrewAI multi‑agent). It is designed to keep the core booking workflow reliable even when optional AI services are unavailable.

## Technologies and Versions
- **FastAPI**: 0.117.1
  - Modern, async web framework; powers all endpoints.
- **Uvicorn**: 0.37.0
  - ASGI server to run FastAPI.
- **Pydantic**: 2.11.9 (pydantic-core 2.33.2)
  - Data validation and typing for request/response models.
- **SQLAlchemy**: 2.0.43
  - ORM for DB access to sections, tables, reservations.
- **Jinja2**: 3.1.6
  - Server-rendered templates for `/chat` UI and base layout.
- **python-multipart**: 0.0.20
  - Form parsing support used by FastAPI.
- Optional AI:
  - **LangChain**: latest (optional)
  - **ChromaDB**: 1.1.0 (optional; vector store)
  - **sentence-transformers**: latest (optional; embeddings)
  - **OpenAI**: latest (optional; LLM generation)
  - **CrewAI**: latest (optional; multi-agent). CrewPlus mode works even if CrewAI isn’t installed.

## Why these technologies
- **FastAPI + Uvicorn + Pydantic**: Type-safe, high performance, and a great developer experience for building API + UI endpoints.
- **SQLAlchemy**: Clean ORM patterns and portability. Easy to switch DB backends later.
- **Jinja2**: Lightweight UI without a heavy front-end build; easy to customize.
- **SVG seat map**: Fast to render on the server, easy to style/color by availability, and simple to display or open in a new tab.
- **RAG with graceful fallback**: When LangChain/Chroma/OpenAI are present, answers can leverage vector retrieval. When not present, the app gracefully degrades without breaking booking flows.
- **CrewPlus multi-agent mode**: Provides a more agentic experience, but also includes an internal heuristic fallback so it always works.

## Project Structure (key paths)
- `app/main.py` — FastAPI app, endpoints, chat logic, seat map SVG (`/api/availability/image`).
- `app/models.py` — SQLAlchemy models (`RestaurantSection`, `Table`, `Reservation`).
- `app/database.py` — DB engine/session and `init_db()`.
- `app/reservation_service.py` — Booking logic and alternatives/combinations.
- `app/nlp_service.py` — Extracts party size, section/view, date, time from NL queries.
- `app/templates/` — Jinja2 templates (`chat.html`, `base.html`, `index.html`).
- `app/rag_system_simple.py` — Deterministic fallback RAG.
- `app/rag_langchain.py` — Optional LangChain-backed QA adapter.
- `app/rag_langchain_vector.py` — Optional Vector RAG (Chroma/FAISS) adapter.
- `app/rag_crew_plus.py` — Multi-agent workflow with built-in fallback.

## RAG/AI Modes
Set via environment variable `RAG_MODE` in the shell before launching:
- `auto` (default): Try full RAG (if present), fallback to simple.
- `simple`: Use `SimpleRestaurantRAGSystem`.
- `full`: Use `RestaurantRAGSystem` if implemented in your repo.
- `langchain`: Use `LangChainRAG` (needs LangChain + optional API key).
- `langchain_chroma`: Use `LangChainVectorRAG` with Chroma.
- `langchain_faiss`: Use `LangChainVectorRAG` with FAISS.
- `crew`: Use the basic CrewAI agent if installed.
- `crew_plus`: Use CrewPlus; if CrewAI isn’t installed, an internal heuristic pipeline keeps it working.

Vector store env (for LangChain vector modes):
- `LCVS_PATH` — Index path (default: `vector_store`)
- `LCVS_DOCS_PATH` — Docs folder to build an index if missing (default: `docs`)
- `LC_EMB_MODEL` — Embedding model (default: `sentence-transformers/all-MiniLM-L6-v2`)
- `OPENAI_API_KEY` — Optional to enable LLM generation in LangChain adapters.

## Workflow
1. User visits `/chat`.
2. Messages go to `/api/chat` (see `chat_api()` in `app/main.py`).
3. Booking/availability intents are parsed (`RestaurantNLPService`).
4. The system queries DB, proposes tables or combinations/alternatives.
5. For availability questions, the response includes `image_url` for the seat map:
   - `/api/availability/image?date=YYYY-MM-DD&time=HH:MM[&view=Section]`
   - Also supports `at=YYYY-MM-DDTHH:MM` and `section=`
6. The chat UI fetches the SVG, inlines it, and also shows a direct link to open in a new tab.
7. Optional RAG answers are used for general questions depending on `RAG_MODE`.

## Run Commands (Windows PowerShell)
Use your current Python (3.13 supported with the versions above). From project root:

1) Create and activate venv
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
```

2) Install core packages
```powershell
python -m pip install "fastapi>=0.115,<1" "uvicorn[standard]>=0.30" "sqlalchemy>=2.0" jinja2 "pydantic>=2.5,<3" "python-multipart>=0.0.6"
```

3) Optional: AI integrations
```powershell
# LangChain + embeddings + OpenAI client
python -m pip install langchain langchain-community sentence-transformers openai
# Chroma vector store
python -m pip install chromadb
# CrewAI (optional; crew_plus works even without this)
python -m pip install crewai
```

4) Select a mode (pick one or leave default auto)
```powershell
$env:RAG_MODE = "crew_plus"          # Always works (uses CrewAI if installed)
# or
$env:RAG_MODE = "langchain_chroma"   # Chroma vector store mode
$env:LCVS_PATH = "vector_store"
$env:LCVS_DOCS_PATH = "docs"
```

5) Run the server
```powershell
python -m uvicorn app.main:app --reload
```

6) Open in browser
- Chat UI: http://127.0.0.1:8000/chat
- Docs: http://127.0.0.1:8000/docs

## Seat Map Visualization
- Endpoint: `GET /api/availability/image`
- Params:
  - `date=YYYY-MM-DD`, `time=HH:MM` or `at=YYYY-MM-DDTHH:MM`
  - Optional `view=` or `section=` to highlight a section
- Colors: Booked = blue, Available = brown.
- The chat replies include `image_url`, and the UI inlines the SVG and provides a direct link to open it.

## Example Questions and Answers
The assistant is tuned to reply with assertive, booking-oriented phrasing.
- Any tables left in the garden for tonight?
  - Yes, we have limited tables available in the garden tonight. How many seats would you like to book?
- Is the private room available tomorrow at 8?
  - Yes, the private room is available tomorrow at 8 pm. Would you like me to reserve it for you?
- Can I book something indoors this weekend?
  - Yes, indoor seating is available this weekend. Could you confirm the number of guests and preferred time?
- How many seats are available in the lake view section right now?
  - Currently, we have X seats available in the lake view section. Would you like me to reserve some for you?
- Is there any chance I can get a private table at 9 pm?
  - Yes, a private table is available at 9 pm. Shall I confirm your booking?
- Do you have any openings for lunch in the garden view area?
  - Yes, we have lunch slots open in the garden view area. What time would you prefer?
- Are there seats for six people indoors tomorrow?
  - Yes, we can accommodate 6 people indoors tomorrow. Should I make the reservation?
- Is the private hall free on Sunday for dinner?
  - Yes, the private hall is available on Sunday for dinner. Would you like to book it?
- Do you have a romantic corner table by the lake?
  - Yes, we do have romantic corner tables by the lake. Would you like me to book one for you?

## Troubleshooting
- Pydantic-core import error on Windows (Python 3.13):
  - Ensure you’re inside the venv and installed the versions listed above.
  - Upgrade tooling: `python -m pip install --upgrade pip setuptools wheel`.
- Seat map not visible:
  - Ensure you ask with a time so the bot returns `image_url` (the UI now also shows a direct link).
  - Direct test: `http://127.0.0.1:8000/api/availability/image` (defaults to current date/time) or add `?view=Lake%20View`.
- Vector RAG not answering:
  - Add `.md` or `.txt` files to `docs/` and set `RAG_MODE=langchain_chroma`.
  - Optionally set `OPENAI_API_KEY` if you want LLM-generated responses.

## Detailed Explanation — How it works
1. **Chat parsing**: `RestaurantNLPService` extracts party size, view, date, and time.
2. **Availability**: `ReservationService` and direct SQLAlchemy queries compute free tables for a date/time and section.
3. **Seat map**: `/api/availability/image` renders an SVG seat map, with booked tables (blue), available (brown), per-section counts, and a section highlight; chair icons are added around each table roughly proportional to capacity.
4. **Booking**: When the user confirms, a `Reservation` is created and stored; seats update immediately in subsequent images.
5. **RAG**: Depending on `RAG_MODE`, the assistant answers general questions using simple deterministic knowledge, LangChain adapters, vector retrieval, or the CrewPlus pipeline. CrewPlus includes a heuristic fallback so it never blocks the flow.

---
If you want me to consolidate this into the root `README.md`, I can replace or merge its content while keeping the Windows run instructions and the new AI modes documented.
