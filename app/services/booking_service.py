from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import List, Dict, Optional, Tuple
from ..models import Table, Reservation, RestaurantSection
from sqlalchemy import and_, or_, func, case
import logging

logger = logging.getLogger(__name__)

class BookingService:
    def __init__(self, db: Session):
        self.db = db
        # Define section priorities (lower number means higher priority)
        self.section_priority = {
            "Lake View": 1,
            "Garden View": 2,
            "Indoors": 3,
            "Private": 4
        }
        # Define time slots (in minutes from opening time)
        self.time_slots = [
            "11:00", "11:30", "12:00", "12:30", "13:00", "13:30", "14:00",  # Lunch
            "18:00", "18:30", "19:00", "19:30", "20:00", "20:30", "21:00", "21:30"  # Dinner
        ]

    def get_available_tables(self, party_size: int, reservation_date: datetime, 
                           reservation_time: str, duration: int = 90) -> List[Dict]:
        """
        Find available tables based on party size, date, and time.
        Returns a list of available tables with their sections.
        """
        # Convert time string to datetime for comparison
        time_obj = datetime.strptime(reservation_time, "%H:%M").time()
        start_datetime = datetime.combine(reservation_date, time_obj)
        end_datetime = start_datetime + timedelta(minutes=duration)
        
        # Get all tables that can accommodate the party size
        query = self.db.query(Table).join(RestaurantSection).filter(
            Table.is_active == True,
            or_(
                Table.capacity >= party_size,
                and_(
                    Table.section.has(RestaurantSection.can_combine_tables == True),
                    Table.capacity * 2 >= party_size  # Can combine tables if needed
                )
            )
        ).order_by(
            # Order by section priority, then by table capacity
            case(
                [(RestaurantSection.name == section, i) 
                 for i, section in enumerate(["Lake View", "Garden View", "Indoors", "Private"])],
                else_=len(self.section_priority)
            ),
            Table.capacity
        )
        
        available_tables = []
        
        for table in query.all():
            # Check if table is available for the requested time
            is_available = not self.db.query(Reservation).filter(
                Reservation.table_id == table.id,
                Reservation.status.in_(["confirmed", "pending"]),
                func.date(Reservation.reservation_date) == reservation_date.date(),
                or_(
                    # Check for overlapping time slots
                    and_(
                        func.time(Reservation.reservation_time) <= time_obj,
                        func.time(Reservation.reservation_time) > time_obj - timedelta(minutes=90)
                    ),
                    and_(
                        func.time(Reservation.reservation_time) >= time_obj,
                        func.time(Reservation.reservation_time) < end_datetime.time()
                    )
                )
            ).first()
            
            if is_available:
                available_tables.append({
                    "id": table.id,
                    "table_number": table.table_number,
                    "capacity": table.capacity,
                    "section": table.section.name,
                    "is_combined": table.is_combined,
                    "combined_with": table.combined_with
                })
                
                # If we have enough tables, we can stop searching
                if len(available_tables) >= 10:  # Limit results for performance
                    break
        
        return available_tables

    def find_best_table_combination(self, party_size: int, section_preference: str = None) -> Tuple[List[Table], str]:
        """
        Find the best combination of tables to accommodate the party size.
        Returns a tuple of (list of tables, section_name)
        """
        # Start with the preferred section, fall back to others based on priority
        sections_query = self.db.query(RestaurantSection).filter(
            RestaurantSection.is_active == True
        )
        
        if section_preference and section_preference != "Any":
            sections_query = sections_query.filter(RestaurantSection.name == section_preference)
        
        sections = sections_query.order_by(RestaurantSection.priority).all()
        
        for section in sections:
            # First try to find a single table that can accommodate the party
            single_table = self.db.query(Table).filter(
                Table.section_id == section.id,
                Table.is_active == True,
                Table.is_combined == False,
                Table.capacity >= party_size
            ).order_by(Table.capacity).first()
            
            if single_table:
                return [single_table], section.name
                
            # If no single table is available, try to combine tables
            if section.can_combine_tables and party_size <= 8:  # Max combined table size
                # Try to find 2 tables that can be combined
                tables = self.db.query(Table).filter(
                    Table.section_id == section.id,
                    Table.is_active == True,
                    Table.is_combined == False,
                    Table.capacity * 2 >= party_size
                ).order_by(Table.capacity).limit(2).all()
                
                if len(tables) == 2 and sum(t.capacity for t in tables) >= party_size:
                    return tables, section.name
        
        return None, "No available tables"

    def create_reservation(
        self,
        customer_name: str,
        customer_email: str,
        party_size: int,
        reservation_date: datetime,
        reservation_time: str,
        section_preference: str = None,
        customer_phone: str = None,
        special_requests: str = None
    ) -> Dict:
        """
        Create a new reservation with the given details.
        Returns a dictionary with the reservation details or an error message.
        """
        # Find available tables
        tables, section_name = self.find_best_table_combination(party_size, section_preference)
        
        if not tables:
            # Try to find alternative sections if preferred section is not available
            if section_preference and section_preference != "Any":
                tables, section_name = self.find_best_table_combination(party_size, "Any")
                if not tables:
                    return {"success": False, "message": "No tables available for the requested time and party size."}
            else:
                return {"success": False, "message": "No tables available for the requested time and party size."}
        
        # Create reservation
        try:
            # If combining tables, mark them as combined
            if len(tables) > 1:
                table_numbers = ",".join([t.table_number for t in tables])
                for table in tables:
                    table.is_combined = True
                    table.combined_with = table_numbers
                self.db.commit()
            
            # Use the first table for the reservation
            table = tables[0]
            
            reservation = Reservation(
                customer_name=customer_name,
                customer_email=customer_email,
                customer_phone=customer_phone,
                party_size=party_size,
                reservation_date=reservation_date,
                reservation_time=reservation_time,
                section_preference=section_preference,
                table_id=table.id,
                special_requests=special_requests,
                status="confirmed"
            )
            
            self.db.add(reservation)
            self.db.commit()
            self.db.refresh(reservation)
            
            return {
                "success": True,
                "reservation_id": reservation.id,
                "table_number": table.table_number,
                "section": section_name,
                "is_combined": len(tables) > 1,
                "combined_tables": table.combined_with if len(tables) > 1 else None
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating reservation: {str(e)}")
            return {"success": False, "message": f"An error occurred while creating the reservation: {str(e)}"}

    def get_available_time_slots(self, party_size: int, reservation_date: datetime) -> Dict[str, List[str]]:
        """
        Get all available time slots for a given date and party size.
        Returns a dictionary with section names as keys and lists of available times as values.
        """
        available_slots = {section: [] for section in self.section_priority.keys()}
        
        for time_slot in self.time_slots:
            # Check availability for each section
            for section_name in self.section_priority.keys():
                tables = self.get_available_tables(party_size, reservation_date, time_slot)
                section_tables = [t for t in tables if t["section"] == section_name]
                
                if section_tables:
                    available_slots[section_name].append(time_slot)
        
        return available_slots

    def cancel_reservation(self, reservation_id: int) -> Dict:
        """
        Cancel a reservation by ID.
        Returns a success/error message.
        """
        reservation = self.db.query(Reservation).get(reservation_id)
        
        if not reservation:
            return {"success": False, "message": "Reservation not found."}
        
        if reservation.status == "cancelled":
            return {"success": False, "message": "This reservation has already been cancelled."}
        
        # If this was a combined table, mark the tables as available again
        if reservation.table and reservation.table.is_combined:
            table_numbers = reservation.table.combined_with.split(',')
            tables = self.db.query(Table).filter(Table.table_number.in_(table_numbers)).all()
            for table in tables:
                table.is_combined = False
                table.combined_with = None
        
        reservation.status = "cancelled"
        self.db.commit()
        
        return {"success": True, "message": "Reservation has been cancelled successfully."}

    def get_reservation_details(self, reservation_id: int) -> Dict:
        """
        Get details for a specific reservation.
        """
        reservation = self.db.query(Reservation).get(reservation_id)
        
        if not reservation:
            return {"success": False, "message": "Reservation not found."}
        
        return {
            "success": True,
            "reservation": {
                "id": reservation.id,
                "customer_name": reservation.customer_name,
                "party_size": reservation.party_size,
                "reservation_date": reservation.reservation_date.strftime("%Y-%m-%d"),
                "reservation_time": reservation.reservation_time,
                "section": reservation.table.section.name if reservation.table else None,
                "table_number": reservation.table.table_number if reservation.table else None,
                "is_combined": reservation.table.is_combined if reservation.table else False,
                "combined_tables": reservation.table.combined_with if reservation.table and reservation.table.is_combined else None,
                "status": reservation.status,
                "special_requests": reservation.special_requests
            }
        }
