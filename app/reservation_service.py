from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from . import models, schemas

def get_available_tables(
    db: Session,
    party_size: int,
    reservation_time: datetime,
    preferred_view: Optional[str] = None,
    max_capacity: Optional[int] = None
) -> Tuple[List[models.Table], bool]:
    """
    Find available tables that can accommodate the party size and preferred view.
    
    Args:
        db: Database session
        party_size: Number of people in the party
        reservation_time: Requested reservation time
        preferred_view: Preferred view (window, garden, etc.)
        max_capacity: Maximum capacity to consider when looking for tables
        
    Returns:
        Tuple of (list of available tables, whether an exact match was found)
    """
    # Calculate time window for checking availability (2 hours before and after)
    time_window_start = reservation_time - timedelta(hours=2)
    time_window_end = reservation_time + timedelta(hours=2)
    
    # Find tables that are already booked in the time window
    booked_tables_query = db.query(models.Reservation.table_id).filter(
        models.Reservation.status == "confirmed",
        models.Reservation.reservation_time.between(time_window_start, time_window_end)
    )
    
    # Base query for available tables
    query = db.query(models.Table).filter(
        models.Table.is_available == True,
        ~models.Table.id.in_(booked_tables_query.subquery())
    )
    
    # Filter by preferred view if specified
    if preferred_view:
        query = query.filter(models.Table.view == preferred_view)
    
    # First, try to find an exact match
    exact_matches = query.filter(
        models.Table.capacity >= party_size,
        models.Table.capacity <= (max_capacity or party_size * 2)  # Don't suggest tables that are too large
    ).order_by(models.Table.capacity).all()
    
    if exact_matches:
        return exact_matches, True
    
    # If no exact match, try to find multiple tables that can be combined
    if not max_capacity or max_capacity < party_size * 2:
        # Get all available tables that are smaller than needed
        smaller_tables = query.filter(
            models.Table.capacity < party_size,
            models.Table.capacity >= 2  # Don't suggest tables smaller than 2
        ).order_by(models.Table.capacity.desc()).all()
        
        if smaller_tables:
            return smaller_tables, False
    
    # If still no matches, try larger tables
    larger_tables = query.filter(
        models.Table.capacity > party_size
    ).order_by(models.Table.capacity).all()
    
    return larger_tables, False

def find_best_table_combination(
    db: Session,
    party_size: int,
    reservation_time: datetime,
    preferred_view: Optional[str] = None
) -> schemas.TableSuggestion:
    """
    Find the best table combination for a given party size and preferred view.
    
    Args:
        db: Database session
        party_size: Number of people in the party
        reservation_time: Requested reservation time
        preferred_view: Preferred view (window, garden, etc.)
        
    Returns:
        TableSuggestion object with the best table combination
    """
    # First try to find an exact match
    tables, is_exact_match = get_available_tables(
        db, party_size, reservation_time, preferred_view
    )
    
    if is_exact_match and tables:
        return schemas.TableSuggestion(
            tables=[tables[0]],
            total_capacity=tables[0].capacity,
            is_exact_match=True,
            message="Perfect match found!"
        )
    
    # If no exact match, try to combine tables
    if not is_exact_match and tables:
        selected_tables = []
        remaining_people = party_size
        
        # Sort tables by capacity in descending order
        sorted_tables = sorted(tables, key=lambda x: x.capacity, reverse=True)
        
        for table in sorted_tables:
            if remaining_people <= 0:
                break
                
            if table.capacity <= remaining_people:
                selected_tables.append(table)
                remaining_people -= table.capacity
            
            # If we have enough capacity with the current selection
            if sum(t.capacity for t in selected_tables) >= party_size:
                break
        
        if selected_tables and sum(t.capacity for t in selected_tables) >= party_size:
            return schemas.TableSuggestion(
                tables=selected_tables,
                total_capacity=sum(t.capacity for t in selected_tables),
                is_exact_match=False,
                message=f"We can accommodate your party with {len(selected_tables)} tables."
            )
    
    # If we get here, no suitable tables were found for this view. Try other views.
    other_view_suggestions: List[models.Table] = []
    if preferred_view:
        other_tables, _ = get_available_tables(
            db, party_size, reservation_time, preferred_view=None
        )
        other_view_suggestions = other_tables[:5]

    note = None
    if preferred_view and other_view_suggestions:
        note = "No tables for the requested view. Here are options in other views."

    return schemas.TableSuggestion(
        tables=[],
        total_capacity=0,
        is_exact_match=False,
        message="Sorry, we couldn't find any available tables for your party size at the requested time.",
        other_view_suggestions=other_view_suggestions,
        note=note,
    )

def create_reservation(
    db: Session,
    reservation: schemas.ReservationCreate
) -> schemas.ReservationResponse:
    """
    Create a new reservation.
    
    Args:
        db: Database session
        reservation: Reservation details
        
    Returns:
        ReservationResponse with the result of the operation
    """
    # If client selected a specific table, validate it's available
    if reservation.table_id is not None:
        time_window_start = reservation.reservation_time - timedelta(hours=2)
        time_window_end = reservation.reservation_time + timedelta(hours=2)

        table = db.query(models.Table).filter(models.Table.id == reservation.table_id).first()
        if not table:
            return schemas.ReservationResponse(
                success=False,
                message="Selected table does not exist.",
            )

        # Check capacity
        if table.capacity < reservation.party_size:
            return schemas.ReservationResponse(
                success=False,
                message="Selected table cannot accommodate the party size.",
            )

        # Check view preference if provided
        if getattr(reservation, 'preferred_view', None) and table.view != reservation.preferred_view:
            return schemas.ReservationResponse(
                success=False,
                message="Selected table does not match the preferred view.",
            )

        # Check overlapping bookings
        overlap = db.query(models.Reservation).filter(
            models.Reservation.table_id == table.id,
            models.Reservation.status == "confirmed",
            models.Reservation.reservation_time.between(time_window_start, time_window_end)
        ).first()
        if overlap:
            # Smart suggestions: try same-view split tables or other views
            preferred = table.view if table and getattr(table, 'view', None) else getattr(reservation, 'preferred_view', None)
            suggestion = find_best_table_combination(
                db,
                reservation.party_size,
                reservation.reservation_time,
                preferred_view=preferred,
            )
            return schemas.ReservationResponse(
                success=False,
                message="Selected table is not available at that time. Here are some alternatives (including split tables in the same view if possible).",
                suggestions=suggestion,
            )

        # Create reservation (double-check overlaps to prevent race conditions)
        db_reservation = models.Reservation(
            customer_name=reservation.customer_name,
            customer_email=reservation.customer_email,
            customer_phone=reservation.customer_phone,
            reservation_time=reservation.reservation_time,
            party_size=reservation.party_size,
            table_id=table.id,
            status="confirmed"
        )
        db.add(db_reservation)
        # Re-check overlap right before committing
        overlap2 = db.query(models.Reservation).filter(
            models.Reservation.table_id == table.id,
            models.Reservation.status == "confirmed",
            models.Reservation.reservation_time.between(time_window_start, time_window_end)
        ).first()
        if overlap2:
            db.rollback()
            preferred = table.view if table and getattr(table, 'view', None) else getattr(reservation, 'preferred_view', None)
            suggestion = find_best_table_combination(
                db,
                reservation.party_size,
                reservation.reservation_time,
                preferred_view=preferred,
            )
            return schemas.ReservationResponse(
                success=False,
                message="Selected table was just booked by someone else. Here are some alternatives (including split tables in the same view if possible).",
                suggestions=suggestion,
            )
        # Save items if provided
        if getattr(reservation, 'items', None):
            for item in reservation.items or []:
                if not item:
                    continue
                menu_item_id = int(item.get('menu_item_id'))
                qty = int(item.get('quantity', 1))
                if qty <= 0:
                    continue
                db.add(models.ReservationItem(
                    reservation=db_reservation,
                    menu_item_id=menu_item_id,
                    quantity=qty,
                ))
        db.commit()
        db.refresh(db_reservation)
        return schemas.ReservationResponse(
            success=True,
            message="Reservation confirmed!",
            reservation=db_reservation,
        )

    # Otherwise, compute suggestion and optionally auto-book if exact single match
    suggestion = find_best_table_combination(
        db,
        reservation.party_size,
        reservation.reservation_time,
        getattr(reservation, 'preferred_view', None)
    )

    if not suggestion.tables:
        return schemas.ReservationResponse(
            success=False,
            message="No tables available for the requested time and party size.",
            suggestions=suggestion,
        )

    if suggestion.is_exact_match and len(suggestion.tables) == 1:
        table = suggestion.tables[0]
        db_reservation = models.Reservation(
            customer_name=reservation.customer_name,
            customer_email=reservation.customer_email,
            customer_phone=reservation.customer_phone,
            reservation_time=reservation.reservation_time,
            party_size=reservation.party_size,
            table_id=table.id,
            status="confirmed"
        )
        db.add(db_reservation)
        if getattr(reservation, 'items', None):
            for item in reservation.items or []:
                if not item:
                    continue
                menu_item_id = int(item.get('menu_item_id'))
                qty = int(item.get('quantity', 1))
                if qty <= 0:
                    continue
                db.add(models.ReservationItem(
                    reservation=db_reservation,
                    menu_item_id=menu_item_id,
                    quantity=qty,
                ))
        db.commit()
        db.refresh(db_reservation)
        return schemas.ReservationResponse(
            success=True,
            message="Reservation confirmed!",
            reservation=db_reservation,
            suggestions=suggestion,
        )

    return schemas.ReservationResponse(
        success=False,
        message="We couldn't find an exact match, but here are some alternatives:",
        suggestions=suggestion,
    )

def get_reservation(db: Session, reservation_id: int) -> Optional[models.Reservation]:
    """Get a reservation by ID."""
    return db.query(models.Reservation).filter(models.Reservation.id == reservation_id).first()

def cancel_reservation(db: Session, reservation_id: int) -> bool:
    """Cancel a reservation."""
    reservation = db.query(models.Reservation).filter(
        models.Reservation.id == reservation_id,
        models.Reservation.status == "confirmed"
    ).first()
    
    if not reservation:
        return False
    
    reservation.status = "cancelled"
    db.commit()
    return True


def get_reservation_items(db: Session, reservation_id: int) -> list[tuple[str, int]]:
    """Return list of (menu_name, quantity) for a reservation."""
    q = (
        db.query(models.MenuItem.name, models.ReservationItem.quantity)
        .join(models.ReservationItem, models.MenuItem.id == models.ReservationItem.menu_item_id)
        .filter(models.ReservationItem.reservation_id == reservation_id)
    )
    return [(name, int(qty or 1)) for name, qty in q.all()]

def get_upcoming_reservations(db: Session, hours_ahead: int = 24) -> List[models.Reservation]:
    """Get all reservations in the next N hours."""
    now = datetime.utcnow()
    end_time = now + timedelta(hours=hours_ahead)
    
    return db.query(models.Reservation).filter(
        models.Reservation.status == "confirmed",
        models.Reservation.reservation_time.between(now, end_time)
    ).order_by(models.Reservation.reservation_time).all()


def available_tables_now(db: Session, view: Optional[str] = None) -> List[models.Table]:
    """Return tables currently available in the next ±2 hours window from now, optionally filtered by view."""
    now = datetime.utcnow()
    window_start = now - timedelta(hours=2)
    window_end = now + timedelta(hours=2)
    booked_ids = db.query(models.Reservation.table_id).filter(
        models.Reservation.status == "confirmed",
        models.Reservation.reservation_time.between(window_start, window_end)
    )
    q = db.query(models.Table).filter(
        models.Table.is_available == True,
        ~models.Table.id.in_(booked_ids.subquery())
    )
    if view:
        q = q.filter(models.Table.view == view)
    return q.order_by(models.Table.view, models.Table.capacity).all()


def list_bookings_today_by_table(db: Session, table_id: int) -> List[models.Reservation]:
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return db.query(models.Reservation).filter(
        models.Reservation.status == "confirmed",
        models.Reservation.table_id == table_id,
        models.Reservation.created_at.between(start, end)
    ).order_by(models.Reservation.reservation_time).all()


def list_bookings_today_by_view(db: Session, view: str) -> List[models.Reservation]:
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    # get table ids by view (case-insensitive)
    v = (view or "").lower()
    table_ids = [t.id for t in db.query(models.Table.id).filter(func.lower(models.Table.view) == v).all()]
    if not table_ids:
        return []
    return db.query(models.Reservation).filter(
        models.Reservation.status == "confirmed",
        models.Reservation.table_id.in_(table_ids),
        models.Reservation.created_at.between(start, end)
    ).order_by(models.Reservation.reservation_time).all()


def get_all_views(db: Session) -> List[str]:
    """Return all distinct view names from tables."""
    return [row[0] for row in db.query(models.Table.view).distinct().all()]


def tables_booked_today_count(db: Session) -> int:
    """Return number of UNIQUE tables that have at least one confirmed booking today (UTC)."""
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    rows = db.query(models.Reservation.table_id).filter(
        models.Reservation.status == "confirmed",
        models.Reservation.created_at.between(start, end)
    ).distinct().all()
    return len(rows)


def total_tables_count(db: Session) -> int:
    return db.query(models.Table).count()


def per_view_table_counts(db: Session) -> List[Tuple[str, int]]:
    # returns list of (view, count)
    from sqlalchemy import func
    return db.query(models.Table.view, func.count(models.Table.id)).group_by(models.Table.view).all()


def list_features(db: Session) -> List[str]:
    return [row[0] for row in db.query(models.Feature.name).order_by(models.Feature.name.asc()).all()]

# ---- Weekly reports (last 7 days, UTC) ----
def _week_window() -> tuple[datetime, datetime]:
    end = datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=999999)
    start = end - timedelta(days=6)
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, end


def count_bookings_week(db: Session) -> int:
    start, end = _week_window()
    return db.query(models.Reservation).filter(
        models.Reservation.status == "confirmed",
        models.Reservation.created_at.between(start, end)
    ).count()


def count_people_week(db: Session) -> int:
    start, end = _week_window()
    rows = db.query(models.Reservation.party_size).filter(
        models.Reservation.status == "confirmed",
        models.Reservation.created_at.between(start, end)
    ).all()
    return sum(r[0] for r in rows)


def list_bookings_week(db: Session) -> List[models.Reservation]:
    # See full definition later in file; keeping stub here for backwards compatibility
    start, end = _week_window()
    return db.query(models.Reservation).filter(
        models.Reservation.status == "confirmed",
        models.Reservation.created_at.between(start, end)
    ).order_by(models.Reservation.reservation_time.asc()).all()


def view_stats(db: Session, view: str, when: Optional[datetime] = None) -> dict:
    """
    Return stats for a given view: total tables, booked count, available count.
    Booked is computed within +/- 2 hours of the 'when' time (default: now UTC).
    """
    when = when or datetime.utcnow()
    window_start = when - timedelta(hours=2)
    window_end = when + timedelta(hours=2)

    v = (view or "").lower()
    total = db.query(models.Table).filter(func.lower(models.Table.view) == v).count()
    # Find table ids of this view
    table_ids = [t.id for t in db.query(models.Table.id).filter(func.lower(models.Table.view) == v).all()]
    booked = 0
    if table_ids:
        booked = db.query(models.Reservation).filter(
            models.Reservation.status == "confirmed",
            models.Reservation.table_id.in_(table_ids),
            models.Reservation.reservation_time.between(window_start, window_end)
        ).count()
    return {
        "view": view,
        "total": total,
        "booked": booked,
        "available": max(total - booked, 0),
        "window_hours": 4,
        "reference_time": when.isoformat(),
    }

# New: next 24 hours view stats and booking list
def view_stats_next24(db: Session, view: str) -> dict:
    now = datetime.utcnow()
    end = now + timedelta(hours=24)
    v = (view or "").lower()
    total = db.query(models.Table).filter(func.lower(models.Table.view) == v).count()
    booked_ids = db.query(models.Reservation.table_id).join(models.Table, models.Table.id == models.Reservation.table_id).filter(
        func.lower(models.Table.view) == v,
        models.Reservation.status == "confirmed",
        models.Reservation.reservation_time.between(now, end)
    ).distinct().count()
    available = max(0, total - booked_ids)
    return {"total": total, "booked": booked_ids, "available": available}


def list_bookings_next24_by_view(db: Session, view: str) -> List[models.Reservation]:
    now = datetime.utcnow()
    end = now + timedelta(hours=24)
    v = (view or "").lower()
    q = db.query(models.Reservation).join(models.Table, models.Table.id == models.Reservation.table_id).filter(
        func.lower(models.Table.view) == v,
        models.Reservation.status == "confirmed",
        models.Reservation.reservation_time.between(now, end)
    ).order_by(models.Reservation.reservation_time.asc())
    return q.all()


def view_stats_on_date(db: Session, view: str, day: datetime) -> dict:
    """Compute Total/Booked/Available for the UTC date of 'day' (00:00–24:00)."""
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    v = (view or "").lower()
    total = db.query(models.Table).filter(func.lower(models.Table.view) == v).count()
    booked_ids = db.query(models.Reservation.table_id).join(models.Table, models.Table.id == models.Reservation.table_id).filter(
        func.lower(models.Table.view) == v,
        models.Reservation.status == "confirmed",
        models.Reservation.reservation_time.between(start, end)
    ).distinct().count()
    return {"total": total, "booked": booked_ids, "available": max(0, total - booked_ids)}


def list_bookings_on_date(db: Session, view: str, day: datetime) -> List[models.Reservation]:
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    v = (view or "").lower()
    q = db.query(models.Reservation).join(models.Table, models.Table.id == models.Reservation.table_id).filter(
        func.lower(models.Table.view) == v,
        models.Reservation.status == "confirmed",
        models.Reservation.reservation_time.between(start, end)
    ).order_by(models.Reservation.reservation_time.asc())
    return q.all()


def list_bookings_around_view(db: Session, view: str, center_time: datetime, window_hours: int = 2) -> List[models.Reservation]:
    """List confirmed bookings for a view within +/- window_hours of center_time."""
    start = center_time - timedelta(hours=window_hours)
    end = center_time + timedelta(hours=window_hours)
    q = db.query(models.Reservation).join(models.Table, models.Table.id == models.Reservation.table_id).filter(
        models.Table.view == view,
        models.Reservation.status == "confirmed",
        models.Reservation.reservation_time.between(start, end)
    ).order_by(models.Reservation.reservation_time.asc())
    return q.all()


def count_bookings_today(db: Session) -> int:
    """Return number of confirmed bookings created today (UTC)."""
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return db.query(models.Reservation).filter(
        models.Reservation.status == "confirmed",
        models.Reservation.created_at.between(start, end)
    ).count()


def get_menu(db: Session) -> List[models.MenuItem]:
    return db.query(models.MenuItem).order_by(models.MenuItem.is_special.desc(), models.MenuItem.name).all()


def list_bookings_today(db: Session) -> List[models.Reservation]:
    """Return today's confirmed reservations (UTC) ordered by time."""
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return db.query(models.Reservation).filter(
        models.Reservation.status == "confirmed",
        models.Reservation.created_at.between(start, end)
    ).order_by(models.Reservation.reservation_time).all()


def create_combo_reservations(db: Session, payload: dict) -> dict:
    """
    Create reservations across multiple tables to accommodate a large party.

    Expected payload keys:
    - customer_name, customer_email, customer_phone, reservation_time (ISO), party_size, preferred_view (optional)
    - table_ids: List[int]
    
    Returns a dict with success, message, and reservations list.
    """
    required = [
        'customer_name', 'customer_email', 'customer_phone',
        'reservation_time', 'party_size', 'table_ids'
    ]
    for k in required:
        if k not in payload:
            raise ValueError(f"Missing required field: {k}")

    reservation_time = payload['reservation_time']
    if isinstance(reservation_time, str):
        reservation_time = datetime.fromisoformat(reservation_time.replace('Z', '+00:00'))

    table_ids = payload['table_ids']
    if not isinstance(table_ids, list) or not table_ids:
        raise ValueError("table_ids must be a non-empty list")

    # Validate each table and ensure no overlaps
    time_window_start = reservation_time - timedelta(hours=2)
    time_window_end = reservation_time + timedelta(hours=2)

    tables = db.query(models.Table).filter(models.Table.id.in_(table_ids)).all()
    if len(tables) != len(set(table_ids)):
        raise ValueError("One or more selected tables do not exist")

    # Check overlaps
    for table in tables:
        overlap = db.query(models.Reservation).filter(
            models.Reservation.table_id == table.id,
            models.Reservation.status == "confirmed",
            models.Reservation.reservation_time.between(time_window_start, time_window_end)
        ).first()
        if overlap:
            raise ValueError(f"Table {table.id} is not available at that time")

    # Create reservations (one per table). We split party across tables approximately.
    remaining = int(payload['party_size'])
    created: List[models.Reservation] = []
    try:
        for table in sorted(tables, key=lambda t: t.capacity, reverse=True):
            if remaining <= 0:
                break
            allocate = min(table.capacity, remaining)
            res = models.Reservation(
                customer_name=payload['customer_name'],
                customer_email=payload['customer_email'],
                customer_phone=payload['customer_phone'],
                reservation_time=reservation_time,
                party_size=allocate,
                table_id=table.id,
                status="confirmed"
            )
            db.add(res)
            created.append(res)
            remaining -= allocate

        if remaining > 0:
            raise ValueError("Selected tables' capacities are insufficient for the party size")

        db.commit()
        for r in created:
            db.refresh(r)

        return {
            "success": True,
            "message": f"Created {len(created)} reservations across {len(tables)} tables.",
            "reservations": [
                {
                    "id": r.id,
                    "table_id": r.table_id,
                    "party_size": r.party_size,
                    "reservation_time": r.reservation_time.isoformat(),
                    "status": r.status,
                }
                for r in created
            ]
        }
    except Exception:
        db.rollback()
        raise


# ==========================
# Monthly Reports and Admin
# ==========================

def _month_window() -> tuple[datetime, datetime]:
    now = datetime.utcnow()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # naive month end
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1)
    else:
        next_month = start.replace(month=start.month + 1)
    end = next_month - timedelta(microseconds=1)
    return start, end


def count_bookings_month(db: Session) -> int:
    start, end = _month_window()
    return db.query(models.Reservation).filter(
        models.Reservation.status == "confirmed",
        models.Reservation.created_at.between(start, end)
    ).count()


def count_people_month(db: Session) -> int:
    start, end = _month_window()
    rows = db.query(models.Reservation.party_size).filter(
        models.Reservation.status == "confirmed",
        models.Reservation.created_at.between(start, end)
    ).all()
    return sum(r[0] for r in rows)


def list_bookings_month(db: Session) -> List[models.Reservation]:
    start, end = _month_window()
    return db.query(models.Reservation).filter(
        models.Reservation.status == "confirmed",
        models.Reservation.created_at.between(start, end)
    ).order_by(models.Reservation.created_at.desc()).all()


def list_bookings_week(db: Session) -> List[models.Reservation]:
    start, end = _week_window()
    return db.query(models.Reservation).filter(
        models.Reservation.status == "confirmed",
        models.Reservation.created_at.between(start, end)
    ).order_by(models.Reservation.reservation_time.asc()).all()


def export_reservations_csv(db: Session, start: datetime, end: datetime) -> str:
    rows = db.query(models.Reservation).filter(
        models.Reservation.created_at.between(start, end)
    ).order_by(models.Reservation.created_at).all()
    headers = [
        "id","customer_name","customer_email","customer_phone","reservation_time",
        "party_size","table_id","status","created_at","special_requests"
    ]
    out = [",".join(headers)]
    for r in rows:
        vals = [
            str(r.id),
            (r.customer_name or '').replace(',', ' '),
            (r.customer_email or ''),
            (r.customer_phone or ''),
            r.reservation_time.isoformat() if r.reservation_time else '',
            str(r.party_size),
            str(r.table_id),
            r.status or '',
            r.created_at.isoformat() if r.created_at else '',
            (r.special_requests or '').replace('\n',' ').replace(',', ' ')
        ]
        out.append(",".join(vals))
    return "\n".join(out)


def add_items_to_reservation(db: Session, reservation_id: int, items: list[dict]) -> bool:
    """Append ReservationItem rows to an existing confirmed reservation.
    Items: list of {'menu_item_id': int, 'quantity': int}
    Returns True on success, False if reservation not found.
    """
    res = db.query(models.Reservation).filter(models.Reservation.id == reservation_id).first()
    if not res:
        return False
    for it in items or []:
        try:
            mid = int(it.get('menu_item_id'))
            qty = max(1, int(it.get('quantity', 1)))
        except Exception:
            continue
        db.add(models.ReservationItem(reservation_id=reservation_id, menu_item_id=mid, quantity=qty))
    db.commit()
    return True


def ensure_view(db: Session, view_name: str, capacities: Optional[List[int]] = None) -> dict:
    capacities = capacities or [2, 4, 6]
    feat = db.query(models.Feature).filter(models.Feature.name == view_name).first()
    if not feat:
        feat = models.Feature(name=view_name)
        db.add(feat)
        db.flush()
    created = 0
    if db.query(models.Table).filter(models.Table.view == view_name).count() == 0:
        for c in capacities:
            db.add(models.Table(capacity=c, view=view_name, is_available=True, features=[feat]))
            created += 1
        db.commit()
    return {"view": view_name, "tables_created": created}


def add_table(db: Session, view_name: str, capacity: int) -> models.Table:
    feat = db.query(models.Feature).filter(models.Feature.name == view_name).first()
    if not feat:
        feat = models.Feature(name=view_name)
        db.add(feat)
        db.flush()
    t = models.Table(capacity=capacity, view=view_name, is_available=True, features=[feat])
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def remove_table(db: Session, table_id: int) -> bool:
    t = db.query(models.Table).filter(models.Table.id == table_id).first()
    if not t:
        return False
    # Prevent removal if there are upcoming confirmed reservations within next 48h
    now = datetime.utcnow()
    future_res = db.query(models.Reservation).filter(
        models.Reservation.table_id == table_id,
        models.Reservation.status == "confirmed",
        models.Reservation.reservation_time >= now
    ).first()
    if future_res:
        return False
    db.delete(t)
    db.commit()
    return True


def purge_views(db: Session, views: List[str]) -> dict:
    """Permanently remove tables that belong to the given views and any related
    reservations and reservation items. Returns a summary dict.
    """
    removed_tables = 0
    removed_reservations = 0
    removed_items = 0
    removed_features = 0

    if not views:
        return {"tables": 0, "reservations": 0, "items": 0, "features": 0}

    # Find tables in those views
    tables = db.query(models.Table).filter(models.Table.view.in_(views)).all()
    table_ids = [t.id for t in tables]
    if table_ids:
        # Delete reservation items joined through reservations for these tables
        res_ids = [r.id for r in db.query(models.Reservation.id).filter(models.Reservation.table_id.in_(table_ids)).all()]
        if res_ids:
            removed_items = db.query(models.ReservationItem).filter(models.ReservationItem.reservation_id.in_(res_ids)).delete(synchronize_session=False)
            removed_reservations = db.query(models.Reservation).filter(models.Reservation.id.in_(res_ids)).delete(synchronize_session=False)
        removed_tables = db.query(models.Table).filter(models.Table.id.in_(table_ids)).delete(synchronize_session=False)

    # Remove feature rows matching view names if they exist
    feats = db.query(models.Feature).filter(models.Feature.name.in_(views)).all()
    for f in feats:
        db.delete(f)
        removed_features += 1

    db.commit()
    return {
        "tables": removed_tables,
        "reservations": removed_reservations,
        "items": removed_items,
        "features": removed_features,
    }


def reschedule_reservation(db: Session, reservation_id: int, new_time: datetime) -> tuple[bool, str]:
    """Attempt to move a confirmed reservation to new_time on the same table.
    If the current table is not free in the ±2h window, return (False, reason).
    """
    res = db.query(models.Reservation).filter(models.Reservation.id == reservation_id).first()
    if not res or res.status != "confirmed":
        return False, "Reservation not found or not confirmed."
    # Check overlap for the same table
    window_start = new_time - timedelta(hours=2)
    window_end = new_time + timedelta(hours=2)
    overlap = db.query(models.Reservation).filter(
        models.Reservation.id != res.id,
        models.Reservation.table_id == res.table_id,
        models.Reservation.status == "confirmed",
        models.Reservation.reservation_time.between(window_start, window_end)
    ).first()
    if overlap:
        return False, "That time is not available on your current table."
    res.reservation_time = new_time
    db.commit()
    db.refresh(res)
    return True, ""
