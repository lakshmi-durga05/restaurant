from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import os

from .database import get_db, init_db
from .models import RestaurantSection, Table, Reservation
from .schemas import ReservationCreate, ReservationResponse, FAQQuery, FAQResponse
from .reservation_service import ReservationService
from .schemas import ReservationCreate

# RAG mode selection: "full" | "simple" | "auto" (default)
RAG_MODE = os.getenv("RAG_MODE", "auto").lower()

rag_system = None
if RAG_MODE == "simple":
    from .rag_system_simple import SimpleRestaurantRAGSystem
    rag_system = SimpleRestaurantRAGSystem()
    print("[RAG] Mode: simple (forced by RAG_MODE)")
elif RAG_MODE == "full":
    try:
        from .rag_system import RestaurantRAGSystem
        rag_system = RestaurantRAGSystem()
        print("[RAG] Mode: full (forced by RAG_MODE)")
    except Exception as e:
        from .rag_system_simple import SimpleRestaurantRAGSystem
        rag_system = SimpleRestaurantRAGSystem()
        print(f"[RAG] Mode fallback to simple due to error loading full stack: {e}")
else:  # auto
    try:
        from .rag_system import RestaurantRAGSystem
        rag_system = RestaurantRAGSystem()
        print("[RAG] Mode: full (auto)")
    except Exception as e:
        from .rag_system_simple import SimpleRestaurantRAGSystem
        rag_system = SimpleRestaurantRAGSystem()
        print(f"[RAG] Mode: simple (auto fallback, reason: {e})")
from .nlp_service import RestaurantNLPService

app = FastAPI(
    title="Restaurant Reservation Manager",
    description="AI-powered restaurant reservation system with natural language processing",
    version="1.0.0"
)

# Initialize services
nlp_service = RestaurantNLPService()

# Optional: swap in alternative RAG engines based on env without breaking workflow
try:
    if RAG_MODE == "langchain":
        from .rag_langchain import LangChainRAG
        rag_system = LangChainRAG()
        print("[RAG] Mode: langchain")
    elif RAG_MODE == "langchain_faiss":
        from .rag_langchain_vector import LangChainVectorRAG
        rag_system = LangChainVectorRAG(backend="faiss")
        print("[RAG] Mode: langchain_faiss")
    elif RAG_MODE == "langchain_chroma":
        from .rag_langchain_vector import LangChainVectorRAG
        rag_system = LangChainVectorRAG(backend="chroma")
        print("[RAG] Mode: langchain_chroma")
    elif RAG_MODE == "crew":
        # CrewAI is optional. If import fails, continue with existing rag_system.
        try:
            from crewai import Agent, Task, Crew  # type: ignore
            class _CrewWrapper:
                def __init__(self):
                    self._ok = True
                def answer_question(self, q: str):
                    # Minimal safe agent to avoid breaking workflow
                    try:
                        researcher = Agent(role="Restaurant Researcher", goal="Answer FAQs about the restaurant.")
                        task = Task(description=q, agent=researcher)
                        crew = Crew(agents=[researcher], tasks=[task])
                        res = crew.kickoff()
                        text = str(res)
                        return text.strip(), 0.6
                    except Exception:
                        return ("I can help with that. Our built-in knowledge base is active.", 0.4)
            rag_system = _CrewWrapper()
            print("[RAG] Mode: crew")
        except Exception as _e:
            print(f"[RAG] CrewAI unavailable, continuing with {type(rag_system).__name__}")
    elif RAG_MODE == "crew_plus":
        # Multi-agent pipeline with internal fallback so it always works
        from .rag_crew_plus import CrewPlusRAG
        rag_system = CrewPlusRAG()
        print("[RAG] Mode: crew_plus")
except Exception as _e2:
    print(f"[RAG] Optional provider wiring skipped: {_e2}")

# Templates for web interface
templates = Jinja2Templates(directory="app/templates")

@app.on_event("startup")
async def startup_event():
    """Initialize database and services on startup"""
    init_db()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with reservation interface"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/reservations", response_model=ReservationResponse)
async def create_reservation(
    reservation_data: ReservationCreate,
    db: Session = Depends(get_db)
):
    """Create a new reservation"""
    service = ReservationService(db)
    
    success, message, reservation, alternatives = service.create_reservation(reservation_data)
    
    return ReservationResponse(
        success=success,
        message=message,
        reservation=reservation,
        alternatives=alternatives
    )

@app.post("/api/chatbot", response_model=FAQResponse)
async def chatbot_query(query: FAQQuery):
    """Chatbot endpoint for restaurant queries using RAG system"""
    try:
        answer, confidence = rag_system.answer_question(query.question)
        return FAQResponse(answer=answer, confidence=confidence)
    except Exception as e:
        print(f"Error in chatbot query: {e}")
        return FAQResponse(
            answer="I'm sorry, I'm having trouble processing your question right now. Please feel free to call us directly for assistance.",
            confidence=0.0
        )

@app.post("/api/faq", response_model=FAQResponse)
async def answer_faq(query: FAQQuery):
    """Answer FAQ using RAG system"""
    answer, confidence = rag_system.answer_question(query.question)
    
    return FAQResponse(
        answer=answer,
        confidence=confidence
    )

@app.get("/api/available-times")
async def get_available_times(
    date: str,
    party_size: int,
    section: str = None,
    db: Session = Depends(get_db)
):
    """Get available reservation times for a given date and party size"""
    try:
        reservation_date = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    service = ReservationService(db)
    available_times = service.get_available_times(reservation_date, party_size, section)
    
    return {"available_times": available_times}

@app.get("/api/sections")
async def get_sections(db: Session = Depends(get_db)):
    """Get all restaurant sections"""
    sections = db.query(RestaurantSection).filter(RestaurantSection.is_active == True).all()
    return sections

@app.get("/api/tables")
async def get_tables(section_id: int = None, db: Session = Depends(get_db)):
    """Get tables, optionally filtered by section"""
    query = db.query(Table).filter(Table.is_active == True)
    
    if section_id:
        query = query.filter(Table.section_id == section_id)
    
    tables = query.all()
    return tables

@app.delete("/api/reservations/{reservation_id}")
async def cancel_reservation(reservation_id: int, db: Session = Depends(get_db)):
    """Cancel a reservation"""
    service = ReservationService(db)
    success = service.cancel_reservation(reservation_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Reservation not found")
    
    return {"message": "Reservation cancelled successfully"}

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/admin/customers")
async def get_all_customers(db: Session = Depends(get_db)):
    """Get all customer information and reservations (Admin endpoint)"""
    try:
        # Get all reservations with customer details
        reservations = db.query(Reservation).order_by(Reservation.created_at.desc()).all()

        # Deduplicate customers by email (case-insensitive), fallback to name if email missing
        seen = set()
        customers = []
        for r in reservations:
            key = (r.customer_email or r.customer_name or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            customers.append({
                "reservation_id": r.id,
                "customer_name": r.customer_name,
                "customer_email": r.customer_email,
                "customer_phone": r.customer_phone,
                "party_size": r.party_size,
                "reservation_date": r.reservation_date.strftime("%Y-%m-%d") if r.reservation_date else None,
                "reservation_time": r.reservation_time,
                "section_preference": r.section_preference,
                "status": r.status,
                "table_id": r.table_id,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else None,
                "special_requests": r.special_requests
            })

        return {
            "total_customers": len(customers),
            "customers": customers
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving customer data: {str(e)}")

@app.get("/api/admin/reservations")
async def get_all_reservations(db: Session = Depends(get_db)):
    """Get all reservations with table information (Admin endpoint)"""
    try:
        # Get all reservations with table and section details
        reservations = db.query(Reservation).join(Table, isouter=True).join(RestaurantSection, isouter=True).order_by(Reservation.created_at.desc()).all()
        
        reservation_data = []
        for reservation in reservations:
            reservation_info = {
                "id": reservation.id,
                "customer_name": reservation.customer_name,
                "customer_email": reservation.customer_email,
                "party_size": reservation.party_size,
                "date": reservation.reservation_date.strftime("%Y-%m-%d"),
                "time": reservation.reservation_time,
                "status": reservation.status,
                "created_at": reservation.created_at.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            if reservation.table:
                reservation_info.update({
                    "table_number": reservation.table.table_number,
                    "table_capacity": reservation.table.capacity,
                    "section_name": reservation.table.section.name
                })
            else:
                reservation_info.update({
                    "table_number": "Not assigned",
                    "table_capacity": "N/A",
                    "section_name": reservation.section_preference or "Any"
                })
            
            reservation_data.append(reservation_info)
        
        return {
            "total_reservations": len(reservation_data),
            "reservations": reservation_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving reservation data: {str(e)}")

# ---------------------------
# Seat map image (SVG)
# ---------------------------

@app.get("/api/availability/image")
async def availability_image(
    date: str | None = None,
    time: str | None = None,
    section: str | None = None,
    view: str | None = None,
    at: str | None = None,
    db: Session = Depends(get_db),
):
    """Generate an SVG seat map with live availability.
    - Booked tables are Blue (#1e90ff)
    - Available tables are Brown (#8b5a2b)
    - Requested section (if any) has a highlighted background
    - Per-section and overall available seat counts are displayed
    """
    # Accept either separate date/time or a combined ISO 'at' param
    if at and (not date or not time):
        try:
            dt = datetime.fromisoformat(at)
            date = dt.strftime("%Y-%m-%d")
            time = dt.strftime("%H:%M")
        except Exception:
            pass
    # Default to current local time rounded to next half hour if missing
    if not date or not time:
        now = datetime.now()
        minutes = (now.minute + 29) // 30 * 30
        if minutes == 60:
            now = now.replace(minute=0) + timedelta(hours=1)
        else:
            now = now.replace(minute=minutes)
        date = date or now.strftime("%Y-%m-%d")
        time = time or now.strftime("%H:%M")
    try:
        date_only = datetime.strptime(date, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date. Use YYYY-MM-DD")

    # Normalize section name for highlight
    view = view or section
    highlight = _normalize_view_name(view) if view else None

    # Fetch sections and tables
    sections = db.query(RestaurantSection).filter(RestaurantSection.is_active == True).all()
    tables = db.query(Table).filter(Table.is_active == True).all()
    # Fallback to core sections if DB has none, so the image is always visible
    core_names = ["Lake View", "Indoors", "Garden View", "Private", "Window"]
    if not sections:
        sections = [RestaurantSection(id=100+i, name=n, is_active=True) for i, n in enumerate(core_names)]
        # No tables in fallback; still draw columns

    # Compute booked table IDs at date+time
    booked_rows = db.query(Reservation).filter(
        Reservation.status.in_(["confirmed", "pending", "active"]),
        Reservation.table_id.isnot(None),
        func.date(Reservation.reservation_date) == date_only,
        Reservation.reservation_time == time,
    ).all()
    booked_ids = set([r.table_id for r in booked_rows if r.table_id])

    # Prepare section ordering similar to sample: Lake, Indoors, Garden, Private, others
    priority_names = ["Lake View", "Indoors", "Garden View", "Private", "Window"]
    def _sec_key(s: RestaurantSection):
        try:
            idx = priority_names.index(s.name)
        except ValueError:
            idx = 100
        return (idx, s.priority or 9999, s.name)
    sections_sorted = sorted(sections, key=_sec_key)

    # Group tables by section id
    tables_by_sec: dict[int, list[Table]] = {}
    for t in tables:
        tables_by_sec.setdefault(t.section_id, []).append(t)
    for sid in list(tables_by_sec.keys()):
        tables_by_sec[sid].sort(key=lambda x: (x.table_number or 0, x.id))

    # Colors
    COLOR_BOOKED = "#1e90ff"
    COLOR_AVAIL = "#8b5a2b"
    BG_DEFAULT = "#ffffff"
    BG_HILITE = {
        "Lake View": "#a6e7ff",
        "Garden View": "#a8e6a1",
        "Indoors": "#f8f8f8",
        "Private": "#f2f2f2",
        "Window": "#f8f8f8",
    }

    # Layout metrics
    col_w = 300
    margin = 10
    header_h = 50
    footer_h = 30
    table_w = 46
    table_h = 28
    gap_x = 18
    gap_y = 18

    n_cols = max(1, len(sections_sorted))
    width = max(640, n_cols * col_w + (n_cols + 1) * margin)
    # Estimate rows by largest section
    max_tables = max((len(tables_by_sec.get(s.id, [])) for s in sections_sorted), default=0)
    rows_est = max(2, (max_tables + 2) // 3)
    height = max(360, header_h + rows_est * (table_h + gap_y) + footer_h + 2 * margin)

    # Compute availability counts
    overall_avail_seats = 0
    section_counts: dict[int, dict[str, int]] = {}
    for s in sections_sorted:
        av_seats = 0
        av_tables = 0
        for t in tables_by_sec.get(s.id, []):
            if t.id not in booked_ids:
                av_tables += 1
                av_seats += (t.capacity or 0)
        section_counts[s.id] = {"tables": av_tables, "seats": av_seats}
        overall_avail_seats += av_seats

    # Build SVG
    parts = []
    parts.append(f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>")
    # Outer border
    parts.append(f"<rect x='1' y='1' width='{width-2}' height='{height-2}' fill='#fff' stroke='#000' stroke-width='2' />")
    # Header text
    parts.append(f"<text x='{margin}' y='{header_h/2+8}' font-size='16' font-family='Arial' font-weight='bold'>Availability {date} {time} - Available seats: {overall_avail_seats}</text>")

    # Draw columns for each section
    for i, s in enumerate(sections_sorted):
        x0 = margin + i * (col_w + margin)
        y0 = header_h
        bg = BG_HILITE.get(s.name, BG_DEFAULT) if highlight and s.name == highlight else BG_DEFAULT
        # Background panel
        parts.append(f"<rect x='{x0}' y='{y0}' width='{col_w}' height='{height - header_h - margin}' fill='{bg}' stroke='#000' stroke-width='2' />")
        # Section label
        cnt = section_counts.get(s.id, {"tables": 0, "seats": 0})
        parts.append(f"<text x='{x0 + 8}' y='{height - footer_h}' font-size='14' font-family='Arial' font-weight='bold'>{s.name} — {cnt['tables']} tables / {cnt['seats']} seats</text>")

        # Place tables in grid (3 per row)
        tx = x0 + 16
        ty = y0 + 16
        c = 0
        for t in tables_by_sec.get(s.id, []):
            fill = COLOR_BOOKED if t.id in booked_ids else COLOR_AVAIL
            rx = tx + (c % 3) * (table_w + gap_x)
            ry = ty + (c // 3) * (table_h + gap_y)
            parts.append(f"<rect x='{rx}' y='{ry}' width='{table_w}' height='{table_h}' fill='{fill}' stroke='#000' stroke-width='1' rx='4' ry='4' />")
            label = t.table_number or t.id
            parts.append(f"<text x='{rx + table_w/2}' y='{ry + table_h/2 + 4}' text-anchor='middle' font-size='12' font-family='Arial' fill='#fff'>{label}</text>")

            # Chairs: draw small squares around the table to reflect capacity
            cap = int(getattr(t, 'capacity', 0) or 0)
            if cap > 0:
                ch_w = 8
                ch_h = 8
                ch_gap = 6
                stroke = '#555'
                fill_ch = '#ffffff'

                # Split capacity roughly between top and bottom sides first
                top_n = cap // 2
                bot_n = cap - top_n

                def _row(n, y, inset=2):
                    if n <= 0:
                        return
                    # Evenly spread chairs across table width
                    span = table_w + 12  # slightly wider than table for nicer spacing
                    start_x = rx + (table_w - span)/2 + inset
                    step = span / max(1, n)
                    for i2 in range(n):
                        cx = start_x + i2 * step
                        parts.append(
                            f"<rect x='{cx:.1f}' y='{y:.1f}' width='{ch_w}' height='{ch_h}' fill='{fill_ch}' stroke='{stroke}' stroke-width='1' rx='2' ry='2' />"
                        )

                # Top row (above table)
                _row(top_n, ry - ch_h - ch_gap)
                # Bottom row (below table)
                _row(bot_n, ry + table_h + ch_gap)

                # If many seats, add left/right columns too
                if cap >= 6:
                    # place up to 2 chairs on left/right sides
                    side_y1 = ry + 2
                    side_y2 = ry + table_h - ch_h - 2
                    parts.append(f"<rect x='{rx - ch_w - ch_gap}' y='{side_y1}' width='{ch_w}' height='{ch_h}' fill='{fill_ch}' stroke='{stroke}' stroke-width='1' rx='2' ry='2' />")
                    parts.append(f"<rect x='{rx - ch_w - ch_gap}' y='{side_y2}' width='{ch_w}' height='{ch_h}' fill='{fill_ch}' stroke='{stroke}' stroke-width='1' rx='2' ry='2' />")
                    parts.append(f"<rect x='{rx + table_w + ch_gap}' y='{side_y1}' width='{ch_w}' height='{ch_h}' fill='{fill_ch}' stroke='{stroke}' stroke-width='1' rx='2' ry='2' />")
                    parts.append(f"<rect x='{rx + table_w + ch_gap}' y='{side_y2}' width='{ch_w}' height='{ch_h}' fill='{fill_ch}' stroke='{stroke}' stroke-width='1' rx='2' ry='2' />")
            c += 1

    parts.append("</svg>")
    svg = "".join(parts)
    return Response(content=svg, media_type="image/svg+xml")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# ---------------------------
# Focused Chat Assistant
# ---------------------------

# Simple in-memory session store for chat (stateless fallback-friendly)
_chat_sessions = {}

def _normalize_view_name(v: str | None) -> str | None:
    if not v:
        return None
    t = v.strip().lower()
    if t in ("lake", "lake view", "lakeside"):
        return "Lake View"
    if t in ("garden", "garden view", "outdoor", "patio"):
        return "Garden View"
    if t in ("indoor", "indoors", "normal", "inside"):
        return "Indoors"
    if t in ("private", "gazebo"):
        return "Private"
    if t in ("window", "window view", "by window"):
        return "Window"
    return None

@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

@app.post("/api/chat")
async def chat_api(payload: dict, db: Session = Depends(get_db)):
    """
    Lightweight conversational endpoint that:
    - Parses booking intents via RestaurantNLPService
    - Creates reservations using ReservationService
    - Falls back to RAG FAQ for general questions
    Returns a JSON with: reply, session_id, and optional image_url for seat map
    """
    session_id = payload.get("session_id") or ""
    message = (payload.get("message") or "").strip()
    if not message:
        # Friendly greeting + available views from DB
        try:
            with next(get_db()) as _db:
                sections = _db.query(RestaurantSection).filter(RestaurantSection.is_active == True).order_by(RestaurantSection.priority).all()
                names = [s.name for s in sections] if sections else []
                # Always include core views for clarity
                core = ["Lake View", "Garden View", "Indoors", "Private", "Window"]
                allv = []
                for v in core + names:
                    if v and v not in allv:
                        allv.append(v)
                views = ", ".join(allv)
        except Exception:
            views = "Lake View, Garden View, Indoors, Private, Window"
        # Ensure a session id exists from the very first response
        if not session_id:
            session_id = os.urandom(4).hex()
            _chat_sessions[session_id] = {"id": session_id}
        greet = (
            "Hello! I’m your restaurant assistant. I can book tables, suggest views, show live availability, and answer questions.\n"
            f"Available views right now: {views}.\n"
            "Tell me what you’d like, or say ‘book a table’."
        )
        return JSONResponse({"reply": greet, "session_id": session_id})

    # Track minimal session data
    sess = _chat_sessions.get(session_id or "") or {"id": session_id or os.urandom(4).hex()}

    # Light free-text enrichments: name, email, date, time
    import re as _re
    m_email = _re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", message)
    if m_email and not sess.get("customer_email"):
        sess["customer_email"] = m_email.group(0)
    m_name = _re.search(r"(?:i am|i'm|name is|this is)\s+([A-Za-z][A-Za-z\-'.]*(?:\s+[A-Za-z][A-Za-z\-'.]*)*)", message, flags=_re.IGNORECASE)
    if m_name and not sess.get("customer_name"):
        sess["customer_name"] = m_name.group(1).strip().title()

    # Explicit date like 2025-09-27 or keywords today/tomorrow
    if not sess.get("date"):
        m_date = _re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", message)
        if m_date:
            try:
                sess["date"] = datetime.strptime(m_date.group(1), "%Y-%m-%d").date()
            except Exception:
                pass
        else:
            low = message.lower()
            if "tomorrow" in low:
                sess["date"] = (datetime.now() + timedelta(days=1)).date()
            elif "today" in low:
                sess["date"] = datetime.now().date()

    # Explicit time like 14:00 or 19:30
    if not sess.get("time"):
        m_time = _re.search(r"\b([01]?\d|2[0-3]):[0-5]\d\b", message)
        if m_time:
            # Normalize to HH:MM 24-hour (pad hour)
            hh, mm = m_time.group(0).split(":")
            sess["time"] = f"{int(hh):02d}:{mm}"

    # Extract a phone number (digits) if present and not yet set
    if not sess.get("customer_phone"):
        # Grab groups of digits, prefer 10-15 length
        digs = ''.join(_re.findall(r"\d+", message))
        if digs and 10 <= len(digs) <= 15:
            sess["customer_phone"] = digs

    # Parse booking request (party size/date/time/section)
    parsed = nlp_service.parse_reservation_request(message)
    # Merge into session but don't overwrite existing confirmed values
    for k, v in parsed.items():
        if v and not sess.get(k):
            sess[k] = v

    # Check required booking fields (ask one at a time if needed)
    def _next_missing_prompt(_sess: dict) -> str | None:
        name = _sess.get("customer_name")
        who = f" {name}" if name else ""
        if not _sess.get("party_size"):
            return f"Thanks{who}! How many people are joining?"
        if not _sess.get("date"):
            return f"Great{who}. Which date would you like? Please use YYYY-MM-DD."
        if not _sess.get("time"):
            return f"And what time works for you? Please use HH:MM (24-hour)."
        if not _sess.get("customer_email"):
            return f"Perfect{who}. Could you share an email for the confirmation?"
        if not _sess.get("customer_phone"):
            return f"Got it{who}. Please share a mobile number (with country code if possible)."
        if not _sess.get("customer_name"):
            return "May I have your full name for the booking?"
        return None

    # Decide if the user is in a booking flow
    booking_keywords = ["book", "booking", "reservation", "table", "reserve"]
    has_booking_signals = (
        any(sess.get(k) for k in ["party_size", "date", "time", "section_preference", "preferred_view"]) or
        any(k in message.lower() for k in booking_keywords)
    )

    low_msg = message.lower()

    # Deterministic answers for address and contact details
    ADDRESS = "Lakeview Gardens, 123 Lakeside Road, Green Park, Hyderabad 500001"
    CONTACT_PHONE = "+91-98765-43210"
    CONTACT_EMAIL = "reservations@lakeviewgardens.example"
    if any(kw in low_msg for kw in ["address", "location", "where are you", "how to reach"]):
        reply = f"Our address is: {ADDRESS}. Directions: we are 2 km from Green Park Metro, with parking on-site."
        _chat_sessions[sess["id"]] = sess
        return JSONResponse({"reply": reply, "session_id": sess["id"]})
    if any(kw in low_msg for kw in ["contact", "phone", "call", "mobile", "number"]):
        reply = f"You can reach us at {CONTACT_PHONE}. For email support, write to {CONTACT_EMAIL}."
        _chat_sessions[sess["id"]] = sess
        return JSONResponse({"reply": reply, "session_id": sess["id"]})

    # Suggestions intent: views for occasions and dish ideas
    suggest_cues = ["suggest", "recommend", "which view", "what view", "romantic", "date", "anniversary", "birthday", "quiet", "kids", "photo", "photos"]
    if any(k in low_msg for k in suggest_cues):
        lines = []
        if any(k in low_msg for k in ["romantic", "date", "anniversary"]):
            lines.append("For a romantic setting, choose Lake View at sunset or the Private room for privacy.")
        if any(k in low_msg for k in ["birthday", "party"]):
            lines.append("For birthdays, the Private room works best for decorations, otherwise Garden View for a lively vibe.")
        if any(k in low_msg for k in ["quiet"]):
            lines.append("For a quiet spot, choose Private or a corner table in Lake View.")
        if any(k in low_msg for k in ["kids", "family"]):
            lines.append("Kids-friendly seating is in Garden View with space to move around.")
        if any(k in low_msg for k in ["photo", "photos", "best view"]):
            lines.append("Best photos come from Lake View near sunset and Garden View during golden hour.")
        # Dish ideas
        if any(k in low_msg for k in ["dish", "dishes", "special", "menu", "what special"]):
            lines.append("Guest favorites: Lobster Risotto, Herb-Crusted Rack of Lamb, Smoked Paneer Tikka (veg), Chocolate Lava Cake.")
            lines.append("Say: 'preorder <dish name>' and I’ll have it ready when you arrive.")
        if not lines:
            lines.append("Lake View and Private are romantic, Garden View is lively and kids-friendly, and Indoors is comfortable for all weather.")
        _chat_sessions[sess["id"]] = sess
        return JSONResponse({"reply": "\n".join(lines), "session_id": sess["id"]})

    # Deterministic specials/menu reply to ensure consistent answer
    if any(kw in low_msg for kw in ["special", "speciality", "signature", "dish", "dishes", "menu"]):
        specials = (
            "Our signature dishes include: Lake View Lobster Risotto, Garden Herb-Crusted Rack of Lamb, "
            "Smoked Paneer Tikka (veg), and our famous Chocolate Lava Cake. We also feature monthly seasonal specials.\n"
            "If you like, say: 'preorder <dish name>' and I’ll have it ready when you arrive."
        )
        _chat_sessions[sess["id"]] = sess
        return JSONResponse({"reply": specials, "session_id": sess["id"]})

    # Heuristic: parse weekday names to a concrete date if no date yet
    if not sess.get("date"):
        import re as _re_w
        days = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
        mday = _re_w.search(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", low_msg)
        if mday:
            try:
                from datetime import timedelta as _td
                wd = days.index(mday.group(1))
                now = datetime.now()
                delta = (wd - now.weekday()) % 7
                delta = 7 if delta == 0 else delta
                sess["date"] = (now + _td(days=delta)).date()
            except Exception:
                pass

    # Natural-language availability questions: yes/no + counts, lead into booking
    avail_q_cues = [
        "do you have", "any tables", "is there any", "is the private", "available tomorrow", "available today",
        "available at", "openings", "seats available", "any chance", "can i get", "is the private room available",
    ]
    if any(k in low_msg for k in avail_q_cues):
        # Determine section preference if specified
        target_for_view = None
        for token in ["lake", "lake view", "garden", "garden view", "indoor", "indoors", "private", "gazebo", "window", "window view", "hall", "private hall"]:
            if token in low_msg:
                target_for_view = _normalize_view_name(token if token != "hall" else "private")
                break

        # Heuristics for date/time phrases
        now = datetime.now()
        text = low_msg
        # Date defaults
        if not sess.get("date"):
            if "tomorrow" in text:
                sess["date"] = (now + timedelta(days=1)).date()
            elif "this weekend" in text or "weekend" in text:
                # choose next Saturday
                wd = now.weekday()
                days_until_sat = (5 - wd) % 7 or 7
                sess["date"] = (now + timedelta(days=days_until_sat)).date()
            elif "sunday" in text:
                days = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
                target = 6
                delta = (target - now.weekday()) % 7 or 7
                sess["date"] = (now + timedelta(days=delta)).date()
            elif "tonight" in text or "today" in text:
                sess["date"] = now.date()
            else:
                sess["date"] = now.date()

        # Time defaults
        if not sess.get("time"):
            if "lunch" in text:
                sess["time"] = "13:00"
            elif "dinner" in text or "tonight" in text or "evening" in text:
                sess["time"] = "19:30"
            elif "at 9" in text or "at 9pm" in text or "at 9 pm" in text or "9 pm" in text or "9pm" in text:
                sess["time"] = "21:00"
            elif "at 8" in text or "at 8pm" in text or "at 8 pm" in text or "8 pm" in text or "8pm" in text:
                sess["time"] = "20:00"
            # If still missing, request time
            if not sess.get("time"):
                _chat_sessions[sess["id"]] = sess
                return JSONResponse({
                    "reply": "Please share a time (HH:MM) so I can check availability.",
                    "session_id": sess["id"]
                })

        # Query DB for availability
        try:
            date_only = sess["date"]
            time_str = sess["time"]
            party = int(sess.get("party_size") or 0)
            # Tables in preferred section or all
            q_tables = db.query(Table).join(RestaurantSection).filter(Table.is_active == True)
            if target_for_view:
                q_tables = q_tables.filter(RestaurantSection.name == target_for_view)
            tables = q_tables.all()
            # Booked ids
            booked_rows = db.query(Reservation).filter(
                Reservation.status.in_(["confirmed", "pending", "active"]),
                Reservation.table_id.isnot(None),
                func.date(Reservation.reservation_date) == date_only,
                Reservation.reservation_time == time_str,
            ).all()
            booked_ids = set([r.table_id for r in booked_rows if r.table_id])
            avail = [t for t in tables if t.id not in booked_ids]
            avail_for_party = [t for t in avail if (t.capacity or 0) >= (party or 1)]

            # Build seat map image URL for UI to optionally render
            from urllib.parse import urlencode
            params = {"date": date_only.strftime("%Y-%m-%d"), "time": time_str}
            if target_for_view:
                params["view"] = target_for_view
            image_url = f"/api/availability/image?{urlencode(params)}"

            if party and avail_for_party:
                top = avail_for_party[0]
                sec = top.section.name
                # Friendly, assertive phrasing
                reply = f"Yes, {sec.lower()} is available at {time_str}. Would you like me to reserve it for you? "
                # Prompt for any missing booking detail next
                ask = _next_missing_prompt(sess)
                if ask:
                    reply += ask
                _chat_sessions[sess["id"]] = sess
                return JSONResponse({"reply": reply, "session_id": sess["id"], "image_url": image_url})
            elif not party and avail:
                count_tables = len(avail)
                total_seats = sum([t.capacity or 0 for t in avail])
                sec = target_for_view or "the selected"
                # If user asked 'how many seats', prioritize that wording
                if "how many seats" in low_msg or "how many seat" in low_msg:
                    reply = f"Currently, we have {total_seats} seats available in {sec} at {time_str}. Would you like me to reserve some for you?"
                else:
                    reply = f"Yes, we have {count_tables} tables available in {sec} at {time_str}, totaling {total_seats} seats. How many seats would you like to book?"
                _chat_sessions[sess["id"]] = sess
                return JSONResponse({"reply": reply, "session_id": sess["id"], "image_url": image_url})
            else:
                # Not available – suggest alternatives and combinations
                # Find alternatives in other views
                others = db.query(Table).join(RestaurantSection).filter(Table.is_active == True).all()
                others_av = [t for t in others if t.id not in booked_ids and (t.capacity or 0) >= (party or 1)]
                alts = []
                for t in others_av[:5]:
                    try:
                        alts.append({"table_number": t.table_number, "capacity": t.capacity, "section": t.section.name})
                    except Exception:
                        pass
                reply = "I'm sorry, that exact option isn't available. "
                if alts:
                    reply += "Here are some alternatives: " + ", ".join([f"{a['section']}: {a['table_number']} (cap {a['capacity']})" for a in alts]) + ". "
                    reply += "You can choose one by replying with its table number. "
                # Two-table combos
                combos = []
                for i in range(len(others_av)):
                    for j in range(i+1, len(others_av)):
                        cap = (others_av[i].capacity or 0) + (others_av[j].capacity or 0)
                        if party and cap >= party:
                            excess = cap - party
                            combos.append((excess, cap, others_av[i], others_av[j]))
                combos.sort(key=lambda x: (x[0], x[1]))
                if combos:
                    ctexts = []
                    for ex, cap, a, b in combos[:3]:
                        ctexts.append(f"Combination: {a.section.name} {a.table_number} (cap {a.capacity}) + {b.section.name} {b.table_number} (cap {b.capacity})")
                    reply += "Other options: " + "; ".join(ctexts)
                _chat_sessions[sess["id"]] = sess
                return JSONResponse({"reply": reply, "session_id": sess["id"], "image_url": image_url})
        except Exception as _e:
            _chat_sessions[sess["id"]] = sess
            return JSONResponse({"reply": "I couldn't check that availability just now. Please try again in a moment.", "session_id": sess["id"]})

    # Facilities and policy quick answers
    if any(k in low_msg for k in ["smoking", "smoke"]):
        ans = "Smoking is not allowed indoors. We have a designated smoking area near the garden entrance."
        _chat_sessions[sess["id"]] = sess
        return JSONResponse({"reply": ans, "session_id": sess["id"]})
    if any(k in low_msg for k in ["pet", "pets", "dog", "cat"]):
        ans = "Pets are welcome in the Garden View area (outdoors) on a leash. Pets are not allowed indoors or in the private room."
        _chat_sessions[sess["id"]] = sess
        return JSONResponse({"reply": ans, "session_id": sess["id"]})
    if any(k in low_msg for k in ["parking", "valet"]):
        ans = "We have on-site parking and optional valet service on weekends after 6 PM."
        _chat_sessions[sess["id"]] = sess
        return JSONResponse({"reply": ans, "session_id": sess["id"]})
    if any(k in low_msg for k in ["wheelchair", "accessible", "accessibility"]):
        ans = "Yes, our entrances and restrooms are wheelchair accessible. Please let us know if you need assistance."
        _chat_sessions[sess["id"]] = sess
        return JSONResponse({"reply": ans, "session_id": sess["id"]})
    if any(k in low_msg for k in ["music", "speaker", "speakers", "soundproof"]):
        ans = "The private dining room is semi-soundproof and supports background music via Bluetooth speaker on request."
        _chat_sessions[sess["id"]] = sess
        return JSONResponse({"reply": ans, "session_id": sess["id"]})
    if any(k in low_msg for k in ["deposit", "advance", "pay in advance", "refund", "cancellation charge", "upi", "pay online", "payment"]):
        ans = (
            "Private room requires a refundable deposit. We accept UPI and online payments. "
            "Standard reservations have no advance charge. Cancellation is free up to 3 hours before your slot."
        )
        _chat_sessions[sess["id"]] = sess
        return JSONResponse({"reply": ans, "session_id": sess["id"]})

    # Who booked today – list customer names (by reservation_date OR created_at)
    if any(k in low_msg for k in ["who booked today", "names booked today", "who all booked today", "booked today names"]):
        try:
            with next(get_db()) as _db:
                today = datetime.now().date()
                rows = _db.query(Reservation.customer_name).filter(
                    Reservation.status.in_(["confirmed", "pending", "active"]),
                    Reservation.customer_name.isnot(None),
                    (
                        func.date(Reservation.reservation_date) == today
                    ) | (
                        func.date(Reservation.created_at) == today
                    )
                ).distinct().order_by(Reservation.customer_name.asc()).all()
                names = [r[0] for r in rows if r and r[0]]
                reply = "Bookings today: " + (", ".join(names) if names else "No bookings yet.")
        except Exception:
            reply = "I couldn't fetch today's bookings right now."
        _chat_sessions[sess["id"]] = sess
        return JSONResponse({"reply": reply, "session_id": sess["id"]})

    # Cancellation intent: by reservation ID or by latest for this user
    if any(k in low_msg for k in ["cancel", "call off", "drop my booking"]):
        import re as _re_c
        m_id = _re_c.search(r"\b(?:id|booking)\s*(\d+)\b", low_msg)
        try:
            with next(get_db()) as _db:
                target_id = None
                if m_id:
                    target_id = int(m_id.group(1))
                else:
                    # Fallback to latest reservation for this user
                    cust_email = sess.get("customer_email")
                    cust_name = sess.get("customer_name")
                    q = _db.query(Reservation)
                    if cust_email:
                        q = q.filter(Reservation.customer_email == cust_email)
                    elif cust_name:
                        q = q.filter(Reservation.customer_name == cust_name)
                    r = q.order_by(Reservation.id.desc()).first()
                    if r:
                        target_id = r.id
                if target_id:
                    svc = ReservationService(_db)
                    ok = svc.cancel_reservation(target_id)
                    _chat_sessions[sess["id"]] = sess
                    if ok:
                        return JSONResponse({"reply": f"Your reservation ID {target_id} has been cancelled.", "session_id": sess["id"]})
                    else:
                        return JSONResponse({"reply": f"I couldn't find or cancel reservation ID {target_id}.", "session_id": sess["id"]})
        except Exception:
            _chat_sessions[sess["id"]] = sess
            return JSONResponse({"reply": "Sorry, I couldn't cancel that right now.", "session_id": sess["id"]})

    # Reschedule intent: change time/date/view/party; create new then cancel old
    if any(k in low_msg for k in ["reschedule", "re-schedule", "change", "update", "move", "shift"]):
        import re as _re_r
        # Optional explicit ID
        m_id2 = _re_r.search(r"\b(?:id|booking)\s*(\d+)\b", low_msg)
        res_id = int(m_id2.group(1)) if m_id2 else None
        try:
            with next(get_db()) as _db:
                # Find source reservation
                src = None
                if res_id:
                    src = _db.query(Reservation).filter(Reservation.id == res_id).first()
                else:
                    cust_email = sess.get("customer_email")
                    cust_name = sess.get("customer_name")
                    q = _db.query(Reservation)
                    if cust_email:
                        q = q.filter(Reservation.customer_email == cust_email)
                    elif cust_name:
                        q = q.filter(Reservation.customer_name == cust_name)
                    src = q.order_by(Reservation.id.desc()).first()
                if not src:
                    _chat_sessions[sess["id"]] = sess
                    return JSONResponse({"reply": "I couldn't find your reservation to reschedule. Please share the booking ID.", "session_id": sess["id"]})

                # Parse desired new details from the current message
                new_parsed = nlp_service.parse_reservation_request(message)
                # Seed from source if not provided
                new_data = {
                    "customer_name": src.customer_name,
                    "customer_email": src.customer_email,
                    "customer_phone": src.customer_phone or sess.get("customer_phone"),
                    "party_size": new_parsed.get("party_size") or src.party_size,
                    "date": new_parsed.get("date") or src.reservation_date,
                    "time": new_parsed.get("time") or src.reservation_time,
                    "section_preference": _normalize_view_name(new_parsed.get("section_preference") or new_parsed.get("preferred_view") or src.section_preference) or "any",
                }

                svc = ReservationService(_db)
                success2, msg2, new_res, alts2 = svc.create_reservation(ReservationCreate(
                    customer_name=new_data["customer_name"],
                    customer_email=new_data["customer_email"],
                    customer_phone=new_data["customer_phone"],
                    party_size=int(new_data["party_size"]),
                    reservation_date=new_data["date"],
                    reservation_time=new_data["time"],
                    section_preference=new_data["section_preference"],
                    special_requests=None,
                ))
                if success2 and new_res:
                    # Cancel the old booking now
                    svc.cancel_reservation(src.id)
                    sess["last_reservation_id"] = new_res.id
                    _chat_sessions[sess["id"]] = sess
                    return JSONResponse({"reply": f"Rescheduled! New ID {new_res.id}. Old booking {src.id} is cancelled.", "session_id": sess["id"]})
                else:
                    _chat_sessions[sess["id"]] = sess
                    out = {"reply": f"I couldn't reschedule directly: {msg2}", "session_id": sess["id"]}
                    if alts2:
                        out["alternatives"] = [{"table_number": t.table_number, "capacity": t.capacity, "section": t.section.name} for t in alts2[:5]]
                        sess["pending_alternatives"] = out["alternatives"]
                    return JSONResponse(out)
        except Exception as _e:
            _chat_sessions[sess["id"]] = sess
            return JSONResponse({"reply": "Sorry, I couldn't process a reschedule right now.", "session_id": sess["id"]})
    # Availability intent: show seat map (either all views or a specific one)
    availability_cues = ["available", "availability", "free tables", "free seats", "show seats", "show availability", "available tables", "available seats", "all views", "entire hotel"]
    if any(kw in low_msg for kw in availability_cues):
        # Determine target view if the user mentioned one
        target_for_view = None
        for token in ["lake", "lake view", "garden", "garden view", "indoor", "indoors", "private", "gazebo", "window", "window view"]:
            if token in low_msg:
                target_for_view = _normalize_view_name(token)
                break
        # Use known date/time if provided, else now
        try:
            from datetime import datetime as _dt
            at_iso = _dt.now().isoformat()
            if sess.get("date") and sess.get("time"):
                at_iso = f"{sess['date'].strftime('%Y-%m-%d')}T{sess['time']}:00"
        except Exception:
            at_iso = datetime.now().isoformat()
        _chat_sessions[sess["id"]] = sess
        if target_for_view:
            return JSONResponse({
                "reply": f"Here’s the current availability for {target_for_view}.",
                "session_id": sess["id"],
                "image_url": f"/api/availability/image?view={target_for_view}&at={at_iso}"
            })
        else:
            return JSONResponse({
                "reply": "Here’s the current availability across all views.",
                "session_id": sess["id"],
                "image_url": f"/api/availability/image?view=all&at={at_iso}"
            })

    # If user is responding to alternatives with a table number, try to confirm using that preference
    if sess.get("pending_alternatives"):
        try:
            import re as _re2
            alts = sess.get("pending_alternatives") or []
            # Extract token like GV-4A or LV-12A etc.
            m_tab = _re2.search(r"\b([A-Za-z]{1,3}-?\d+[A-Za-z]?)\b", message)
            if m_tab:
                pick = m_tab.group(1).upper()
                chosen = next((a for a in alts if (a.get("table_number") or "").upper() == pick), None)
                if chosen:
                    sess["section_preference"] = chosen.get("section")
                    sess["pending_alternatives"] = None
                    # fall through to booking below with updated preference
        except Exception:
            pass

    # If user asked operational stats explicitly (e.g., "how many bookings today"), handle quickly
    if any(kw in message.lower() for kw in ["how many bookings today", "bookings today", "how many bookings happened today"]):
        try:
            with next(get_db()) as _db:
                today = datetime.now().date()
                count = _db.query(func.count(Reservation.id)).filter(
                    Reservation.status.in_(["confirmed", "pending", "active"]),
                    (
                        func.date(Reservation.reservation_date) == today
                    ) | (
                        func.date(Reservation.created_at) == today
                    )
                ).scalar()
        except Exception:
            count = None
        _chat_sessions[sess["id"]] = sess
        reply = f"We have {count} booking(s) today." if count is not None else "I couldn't fetch booking stats right now."
        return JSONResponse({"reply": reply, "session_id": sess["id"]})

    # Only if NOT in a booking intent, handle FAQ here
    faq_cues = [
        "hour", "timing", "open", "close", "address", "location", "contact", "phone",
        "policy", "vegetarian", "vegan", "menu", "signature", "special", "dish",
        "how much", "price", "directions"
    ]
    is_question = "?" in message
    if not has_booking_signals and (is_question or any(k in message.lower() for k in faq_cues)):
        try:
            answer, _conf = rag_system.answer_question(message)
            # If user asked about specials, add preorder tip
            if any(k in low_msg for k in ["special", "signature", "dish", "dishes", "menu"]):
                answer = answer.strip() + "\nIf you like, say: 'preorder <dish name>' and I’ll have it ready when you arrive."
            _chat_sessions[sess["id"]] = sess
            return JSONResponse({"reply": answer, "session_id": sess["id"]})
        except Exception:
            pass

    # Preorder flow: if user says 'preorder <dish>' and has a recent reservation, store it
    if any(k in low_msg for k in ["preorder", "pre-order", "pre order"]) or low_msg.startswith("order "):
        try:
            import re as _re3
            m_dish = _re3.search(r"(?:pre\s*-?order|order)\s+(.+)$", message, flags=_re3.IGNORECASE)
            dish = (m_dish.group(1).strip() if m_dish else "").strip().rstrip('.')
            if dish:
                # Attach to the latest reservation for this email/name if available
                cust_email = sess.get("customer_email")
                cust_name = sess.get("customer_name")
                r = db.query(Reservation).filter(
                    (Reservation.customer_email == cust_email) | (Reservation.customer_name == cust_name)
                ).order_by(Reservation.id.desc()).first()
                if r:
                    note = (r.special_requests or "").strip()
                    sep = "\n" if note else ""
                    r.special_requests = f"{note}{sep}Preorder: {dish}"
                    db.add(r)
                    db.commit()
                    _chat_sessions[sess["id"]] = sess
                    return JSONResponse({"reply": f"Got it. I’ve added a preorder for '{dish}'. It’ll be ready shortly after you’re seated.", "session_id": sess["id"]})
                else:
                    _chat_sessions[sess["id"]] = sess
                    return JSONResponse({"reply": "I can place that preorder once we have a reservation. Would you like me to book a table first?", "session_id": sess["id"]})
        except Exception:
            pass

    missing_prompt = _next_missing_prompt(sess)

    # Determine if we have all fields to proceed
    ready_to_book = bool(sess.get("party_size") and sess.get("date") and sess.get("time") and sess.get("customer_email") and sess.get("customer_phone"))

    # If user seems to be booking but details are missing, ask for exactly one next detail
    if has_booking_signals and not ready_to_book:
        _chat_sessions[sess["id"]] = sess
        return JSONResponse({
            "reply": missing_prompt or "Sure—tell me your party size, date, time, and an email to confirm.",
            "session_id": sess["id"]
        })

    # If not in booking flow and not ready, avoid forcing booking—acknowledge and guide
    if not has_booking_signals and not ready_to_book:
        name = sess.get("customer_name")
        ack = f"Nice to meet you {name}! " if name else ""
        tip = "You can ask me anything, or say something like: 'Table for 2 tomorrow at 19:30 in lake view. My email is you@example.com'."
        _chat_sessions[sess["id"]] = sess
        return JSONResponse({"reply": ack + tip, "session_id": sess["id"]})

    # We have enough info – attempt booking
    try:
        section_pref = _normalize_view_name(sess.get("section_preference") or sess.get("preferred_view"))
        reservation_data = ReservationCreate(
            customer_name=sess.get("customer_name") or "Guest",
            customer_email=sess.get("customer_email") or "guest@example.com",
            customer_phone=sess.get("customer_phone"),
            party_size=int(sess.get("party_size")),
            reservation_date=sess.get("date"),
            reservation_time=sess.get("time"),
            section_preference=section_pref or "any",
            special_requests=None,
        )
        service = ReservationService(db)
        success, message_text, reservation, alternatives = service.create_reservation(reservation_data)

        _chat_sessions[sess["id"]] = sess
        # Always format a clear confirmation when booking succeeds
        if success and reservation:
            try:
                sec_name = None
                table_num = None
                if getattr(reservation, "table", None):
                    table = reservation.table
                    table_num = getattr(table, "table_number", None)
                    try:
                        sec_name = table.section.name if table.section else None
                    except Exception:
                        sec_name = None
                if not sec_name:
                    sec_name = reservation.section_preference or (sess.get("section_preference") or sess.get("preferred_view") or "Selected section")
                party = reservation.party_size
                rdate = reservation.reservation_date.strftime("%Y-%m-%d") if reservation.reservation_date else (getattr(sess.get("date"), "strftime", lambda x: str(x))("%Y-%m-%d") if sess.get("date") else "")
                rtime = reservation.reservation_time
                base = f"Confirmed! Your booking for {party} guest(s) on {rdate} at {rtime} in {sec_name} is secured."
                if table_num:
                    base += f" Your table number is {table_num}."
                base += f" Reservation ID: {reservation.id}."
                message_text = base
            except Exception:
                pass
        out = {"reply": message_text, "session_id": sess["id"]}

        # If alternatives exist, include a lightweight summary
        if not success and alternatives:
            alts = []
            for t in alternatives[:3]:
                try:
                    alts.append({"table_number": t.table_number, "capacity": t.capacity, "section": t.section.name})
                except Exception:
                    pass
            if alts:
                out["alternatives"] = alts
        # Do not attach any seat map during booking confirmations

        # Add a simple WhatsApp confirmation link the user can tap (no Twilio)
        try:
            if success and reservation:
                phone_raw = sess.get("customer_phone", "")
                phone_digits = ''.join(_re.findall(r"\d+", phone_raw)) or phone_raw
                cname = (sess.get("customer_name") or "Guest").title()
                rdate = sess.get("date")
                rtime = sess.get("time")
                view_txt = section_pref or "Preferred"
                text = (
                    f"Hello {cname}, your table is booked at Lakeview Gardens on {rdate} at {rtime} in {view_txt}. "
                    f"Reservation ID: {reservation.id}. We look forward to hosting you!"
                )
                import urllib.parse as _up
                out["whatsapp_confirm_url"] = f"https://wa.me/{phone_digits}?text={_up.quote(text)}"
        except Exception:
            pass

        return JSONResponse(out)
    except Exception as e:
        _chat_sessions[sess["id"]] = sess
        return JSONResponse({"reply": f"Sorry, I had trouble booking: {e}", "session_id": sess["id"]})


@app.get("/api/availability/image")
async def availability_image(view: str, at: str, db: Session = Depends(get_db)):
    """Return an SVG seat map. Booked = blue, Available = brown."""
    target_view = _normalize_view_name(view) if view != "all" else "all"
    try:
        at_dt = datetime.fromisoformat(at)
        date_only = at_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        time_str = at_dt.strftime("%H:%M")
    except Exception:
        at_dt = datetime.now()
        date_only = at_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        time_str = at_dt.strftime("%H:%M")

    from .models import Table, RestaurantSection, Reservation

    # Rendering constants
    cols = 10
    cell_w, cell_h = 50, 40
    pad = 20
    section_gap = 60

    def render_section(svg_parts, sec, y_offset):
        tables = db.query(Table).filter(Table.section_id == sec.id, Table.is_active == True).order_by(Table.id).all()
        booked_rows = db.query(Reservation).filter(
            Reservation.status.in_(["confirmed", "pending", "active"]),
            Reservation.table_id.isnot(None),
            func.date(Reservation.reservation_date) == func.date(at_dt),
            Reservation.reservation_time == time_str,
        ).all()
        booked_ids = set([r.table_id for r in booked_rows if r.table_id])
        rows = (len(tables) + cols - 1) // cols
        # Section title
        svg_parts.append(f"<text x='{pad}' y='{y_offset}' font-size='16' fill='#111' font-weight='600'>{sec.name}</text>")
        # Draw tables
        for idx, t in enumerate(tables):
            r = idx // cols
            c = idx % cols
            x = pad + c * cell_w
            y = y_offset + 10 + r * cell_h
            color = "#1e3a8a" if t.id in booked_ids else "#8b5e3c"
            svg_parts.append(f"<rect x='{x}' y='{y}' rx='6' ry='6' width='{cell_w-8}' height='{cell_h-8}' fill='{color}' stroke='#333' stroke-width='1'/>")
            svg_parts.append(f"<text x='{x+8}' y='{y+22}' font-size='11' fill='white'>{t.table_number}</text>")
        return rows

    if target_view == "all":
        sections = db.query(RestaurantSection).filter(RestaurantSection.is_active == True).order_by(RestaurantSection.priority).all()
        if not sections:
            return Response(content="<svg xmlns='http://www.w3.org/2000/svg' width='600' height='200'></svg>", media_type="image/svg+xml")
        # Estimate height
        total_rows = 0
        for sec in sections:
            cnt = db.query(Table).filter(Table.section_id == sec.id, Table.is_active == True).count()
            total_rows += (cnt + cols - 1) // cols
        height = pad * 2 + total_rows * cell_h + section_gap * len(sections) + 80
        width = pad * 2 + cols * cell_w
        svg_parts = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}'>"]
        svg_parts.append(f"<text x='{pad}' y='24' font-size='18' fill='#333'>All Views at {time_str}</text>")
        # Legend
        svg_parts.append(f"<rect x='{pad}' y='{height-30}' width='14' height='14' fill='#1e3a8a'/><text x='{pad+20}' y='{height-18}' font-size='12'>Booked</text>")
        svg_parts.append(f"<rect x='{pad+120}' y='{height-30}' width='14' height='14' fill='#8b5e3c'/><text x='{pad+140}' y='{height-18}' font-size='12'>Available</text>")
        y_cursor = pad + 30
        for sec in sections:
            rows = render_section(svg_parts, sec, y_cursor)
            y_cursor += rows * cell_h + section_gap
        svg_parts.append("</svg>")
        svg = "".join(svg_parts)
        return Response(content=svg, media_type="image/svg+xml")
    else:
        # Single section rendering
        sec = db.query(RestaurantSection).filter(RestaurantSection.name == target_view).first()
        if not sec:
            return Response(content="<svg xmlns='http://www.w3.org/2000/svg' width='600' height='200'></svg>", media_type="image/svg+xml")
        tables = db.query(Table).filter(Table.section_id == sec.id, Table.is_active == True).order_by(Table.id).all()
        booked_rows = db.query(Reservation).filter(
            Reservation.status.in_(["confirmed", "pending", "active"]),
            Reservation.table_id.isnot(None),
            Reservation.reservation_date == at_dt.replace(hour=0, minute=0, second=0, microsecond=0),
            Reservation.reservation_time == time_str,
        ).all()
        booked_ids = set([r.table_id for r in booked_rows if r.table_id])
        rows = (len(tables) + cols - 1) // cols
        width = pad * 2 + cols * cell_w
        height = pad * 2 + rows * cell_h + 60
        svg_parts = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}'>"]
        svg_parts.append(f"<text x='{pad}' y='24' font-size='16' fill='#333'>View: {target_view} at {time_str}</text>")
        # Legend
        svg_parts.append(f"<rect x='{pad}' y='{height-30}' width='14' height='14' fill='#1e3a8a'/><text x='{pad+20}' y='{height-18}' font-size='12'>Booked</text>")
        svg_parts.append(f"<rect x='{pad+120}' y='{height-30}' width='14' height='14' fill='#8b5e3c'/><text x='{pad+140}' y='{height-18}' font-size='12'>Available</text>")
        for idx, t in enumerate(tables):
            r = idx // cols
            c = idx % cols
            x = pad + c * cell_w
            y = pad + 30 + r * cell_h
            color = "#1e3a8a" if t.id in booked_ids else "#8b5e3c"
            svg_parts.append(f"<rect x='{x}' y='{y}' rx='6' ry='6' width='{cell_w-8}' height='{cell_h-8}' fill='{color}' stroke='#333' stroke-width='1'/>")
            svg_parts.append(f"<text x='{x+8}' y='{y+22}' font-size='11' fill='white'>{t.table_number}</text>")
        svg_parts.append("</svg>")
        svg = "".join(svg_parts)
        return Response(content=svg, media_type="image/svg+xml")
