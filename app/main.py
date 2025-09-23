from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from datetime import datetime, timedelta
from typing import List, Optional
import uvicorn
import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from . import models, schemas, database, reservation_service, chatbot
from .database import get_db

# Load environment variables
load_dotenv()

# Ensure database tables exist/migrate
models.Base.metadata.create_all(bind=database.engine)

# Purge disallowed views from the database at startup (idempotent)
try:
    with database.SessionLocal() as _db:
        reservation_service.purge_views(_db, ["rooftop", "patio", "palo"])  # remove permanently
except Exception:
    # Do not block app startup if purge fails; it's safe to ignore
    pass

# Initialize FastAPI app
app = FastAPI(
    title="Restaurant Booking API",
    description="API for managing restaurant table reservations",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files if folder exists
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates_dir = "templates"
if not os.path.isdir(templates_dir):
    os.makedirs(templates_dir, exist_ok=True)
templates = Jinja2Templates(directory=templates_dir)

# Root -> redirect to chatbot UI
from starlette.responses import RedirectResponse

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/chat")

# Check table availability
@app.get("/api/availability", response_model=schemas.TableSuggestion)
async def check_availability(
    party_size: int = Query(..., gt=0, le=20, description="Number of people in the party"),
    reservation_time: datetime = Query(..., description="Requested reservation time (ISO 8601 format)"),
    preferred_view: Optional[str] = Query(None, description="Preferred view (window, garden, private, etc.)"),
    db: Session = Depends(database.get_db)
):
    """
    Check table availability for a given party size and time.
    Returns available tables or suggestions if no exact match is found.
    """
    try:
        return reservation_service.find_best_table_combination(
            db=db,
            party_size=party_size,
            reservation_time=reservation_time,
            preferred_view=preferred_view
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# Create a new reservation
@app.post("/api/reservations", response_model=schemas.ReservationResponse, status_code=status.HTTP_201_CREATED)
async def create_reservation(
    reservation: schemas.ReservationCreate,
    db: Session = Depends(database.get_db)
):
    """
    Create a new reservation.
    If an exact table match is not available, returns alternative suggestions.
    """
    try:
        return reservation_service.create_reservation(db=db, reservation=reservation)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# Get reservation by ID
@app.get("/api/reservations/{reservation_id}", response_model=schemas.Reservation)
async def get_reservation(
    reservation_id: int,
    db: Session = Depends(database.get_db)
):
    """Get details of a specific reservation."""
    reservation = reservation_service.get_reservation(db, reservation_id)
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found"
        )
    return reservation

# Cancel a reservation
@app.post("/api/reservations/{reservation_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_reservation(
    reservation_id: int,
    db: Session = Depends(database.get_db)
):
    """Cancel an existing reservation."""
    success = reservation_service.cancel_reservation(db, reservation_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found or already cancelled"
        )
    return {"status": "success", "message": "Reservation cancelled successfully"}

# Get upcoming reservations
@app.get("/api/reservations/upcoming", response_model=List[schemas.Reservation])
async def get_upcoming_reservations(
    hours_ahead: int = Query(24, description="Number of hours to look ahead"),
    db: Session = Depends(database.get_db)
):
    """Get all upcoming reservations within the specified time window."""
    return reservation_service.get_upcoming_reservations(db, hours_ahead)

# Create multiple reservations for a combination of tables
@app.post("/api/reservations/combo", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_combo_reservations(
    payload: dict,
    db: Session = Depends(database.get_db)
):
    """
    Create multiple reservations for a suggested combination of tables.
    Expects payload with ReservationBase fields plus table_ids: List[int].
    """
    try:
        response = reservation_service.create_combo_reservations(db=db, payload=payload)
        return response
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Booking form UI route removed (chatbot-only interface)

# Chatbot web UI
@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

# Chatbot API
@app.post("/api/chatbot/message")
async def chatbot_message(payload: dict, db: Session = Depends(database.get_db)):
    session_id = payload.get("session_id")
    message = payload.get("message", "")
    result = chatbot.handle_message(db, session_id, message)
    return result

# Menu endpoint
@app.get("/api/menu", response_model=List[schemas.MenuItem])
async def get_menu(db: Session = Depends(database.get_db)):
    items = reservation_service.get_menu(db)
    return items

# Admin: view customers (today's bookings)
@app.get("/admin/customers", response_class=HTMLResponse)
async def admin_customers(request: Request, db: Session = Depends(database.get_db)):
    bookings = reservation_service.list_bookings_today(db)
    # enrich with view name from table
    by_id = {t.id: t for t in db.query(models.Table).all()}
    rows = []
    for r in bookings:
        view = by_id.get(r.table_id).view if r.table_id in by_id else "-"
        rows.append({
            "id": r.id,
            "name": r.customer_name,
            "party": r.party_size,
            "time": r.reservation_time.strftime("%Y-%m-%d %H:%M") if r.reservation_time else "",
            "table": r.table_id,
            "view": view,
        })
    return templates.TemplateResponse("customers.html", {"request": request, "rows": rows})

# Admin: download database file
@app.get("/admin/db")
async def admin_db_download():
    try:
        db_path = database.engine.url.database
        filename = os.path.basename(db_path) if db_path else "restaurant_booking.db"
        return FileResponse(db_path, media_type="application/octet-stream", filename=filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Admin: simple DB viewer
@app.get("/admin/db/view", response_class=HTMLResponse)
async def admin_db_view(request: Request, db: Session = Depends(database.get_db)):
    # Pull a small snapshot to avoid heavy pages
    tables = db.query(models.Table).order_by(models.Table.view, models.Table.id).limit(50).all()
    reservations = db.query(models.Reservation).order_by(models.Reservation.created_at.desc()).limit(50).all()
    items = db.query(models.ReservationItem).order_by(models.ReservationItem.id.desc()).limit(50).all()
    return templates.TemplateResponse(
        "db.html",
        {
            "request": request,
            "tables": tables,
            "reservations": reservations,
            "items": items,
        },
    )

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

# Run the application
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
