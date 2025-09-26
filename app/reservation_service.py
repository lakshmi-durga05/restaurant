from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from .models import Table, Reservation, RestaurantSection
from .schemas import ReservationCreate

class ReservationService:
    def __init__(self, db: Session):
        self.db = db
    
    def find_available_table(self, party_size: int, date: datetime, time: str, 
                           section_preference: Optional[str] = None) -> Optional[Table]:
        """Find an available table for the given criteria with priority-based selection"""
        # Get booked table IDs for the time slot
        booked_table_ids = self._get_booked_table_ids(date, time)
        
        # Handle private area separately (special case)
        if party_size >= 20:
            private_table = self._find_private_table(booked_table_ids)
            if private_table:
                return private_table
        
        # Try exact capacity match first
        exact_table = self._find_exact_capacity_table(party_size, booked_table_ids, section_preference)
        if exact_table:
            return exact_table
        
        # Try table combination for 4 people (2*2 seaters)
        if party_size == 4:
            combination = self._find_table_combination_for_4(booked_table_ids, section_preference)
            if combination:
                return combination[0]  # Return first table as representative
        
        # Try larger table if no exact match
        larger_table = self._find_larger_table(party_size, booked_table_ids, section_preference)
        if larger_table:
            return larger_table
        
        return None
    
    def find_alternative_tables(self, party_size: int, date: datetime, time: str,
                              section_preference: Optional[str] = None) -> List[Table]:
        """Find alternative table combinations or different sections with priority-based suggestions"""
        alternatives = []
        booked_table_ids = self._get_booked_table_ids(date, time)
        
        # Get sections in priority order (Lake View -> Garden View -> Indoors)
        sections = self.db.query(RestaurantSection).filter(
            RestaurantSection.is_active == True
        ).order_by(RestaurantSection.priority).all()
        
        # If user has a preference, suggest alternatives in priority order
        if section_preference and section_preference.lower() != "any":
            # Find the preferred section
            preferred_section = None
            for section in sections:
                if section.name.lower() == section_preference.lower():
                    preferred_section = section
                    break
            
            if preferred_section:
                # Suggest alternatives in priority order, excluding the preferred section
                for section in sections:
                    if section.id == preferred_section.id:
                        continue  # Skip the preferred section
                    
                    # Try exact capacity match
                    table = self._find_exact_capacity_table(party_size, booked_table_ids, section.name)
                    if table:
                        alternatives.append(table)
                        if len(alternatives) >= 3:
                            break
                        continue
                    
                    # Try table combination for 4 people
                    if party_size == 4:
                        combination = self._find_table_combination_for_4(booked_table_ids, section.name)
                        if combination:
                            alternatives.append(combination[0])
                            if len(alternatives) >= 3:
                                break
                            continue
                    
                    # Try larger table
                    table = self._find_larger_table(party_size, booked_table_ids, section.name)
                    if table:
                        alternatives.append(table)
                        if len(alternatives) >= 3:
                            break
        else:
            # No preference specified, suggest in priority order
            for section in sections:
                # Try exact capacity match
                table = self._find_exact_capacity_table(party_size, booked_table_ids, section.name)
                if table:
                    alternatives.append(table)
                    if len(alternatives) >= 3:
                        break
                    continue
                
                # Try table combination for 4 people
                if party_size == 4:
                    combination = self._find_table_combination_for_4(booked_table_ids, section.name)
                    if combination:
                        alternatives.append(combination[0])
                        if len(alternatives) >= 3:
                            break
                        continue
                
                # Try larger table
                table = self._find_larger_table(party_size, booked_table_ids, section.name)
                if table:
                    alternatives.append(table)
                    if len(alternatives) >= 3:
                        break
        
        return alternatives[:3]  # Return top 3 alternatives
    
    
    def create_reservation(self, reservation_data: ReservationCreate) -> Tuple[bool, str, Optional[Reservation], List[Table]]:
        """Create a reservation with intelligent table allocation"""
        # First, try to find an exact table match
        table = self.find_available_table(
            reservation_data.party_size,
            reservation_data.reservation_date,
            reservation_data.reservation_time,
            reservation_data.section_preference
        )
        
        if table:
            # Double-check that the table is still available (prevent race conditions)
            if not self._is_table_available(table.id, reservation_data.reservation_date, reservation_data.reservation_time):
                # Table was booked by someone else, find alternatives
                alternatives = self.find_alternative_tables(
                    reservation_data.party_size,
                    reservation_data.reservation_date,
                    reservation_data.reservation_time,
                    reservation_data.section_preference
                )
                return False, "I'm sorry, that table was just booked by another guest. Let me find you alternatives.", None, alternatives
            
            # Handle table combination for 4 people (2*2 seaters)
            if reservation_data.party_size == 4 and table.capacity == 2:
                # This is a combination of two 2-seater tables
                booked_table_ids = self._get_booked_table_ids(reservation_data.reservation_date, reservation_data.reservation_time)
                combination = self._find_table_combination_for_4(booked_table_ids, reservation_data.section_preference)
                
                if combination and len(combination) >= 2:
                    # Create reservation with the first table as primary, but mark as combined
                    reservation = Reservation(
                        **reservation_data.dict(),
                        table_id=combination[0].id,
                        status="confirmed",
                        special_requests=f"Combined tables: {combination[0].table_number} and {combination[1].table_number}"
                    )
                    self.db.add(reservation)
                    self.db.commit()
                    self.db.refresh(reservation)
                    
                    return True, (
                        f"Perfect! I've combined two 2-seater tables in our {table.section.name} section "
                        f"for your party of 4. Your table numbers are {combination[0].table_number} and {combination[1].table_number}."
                    ), reservation, []
            
            # Create reservation with the found table
            reservation = Reservation(
                **reservation_data.dict(),
                table_id=table.id,
                status="confirmed"
            )
            self.db.add(reservation)
            self.db.commit()
            self.db.refresh(reservation)
            
            return True, (
                f"Perfect! I've found a {table.capacity}-seater in our {table.section.name} section "
                f"for you. Your table number is {table.table_number}."
            ), reservation, []
        
        # If no exact match, find alternatives
        alternatives = self.find_alternative_tables(
            reservation_data.party_size,
            reservation_data.reservation_date,
            reservation_data.reservation_time,
            reservation_data.section_preference
        )
        
        if alternatives:
            # Create reservation without table assignment (pending customer choice)
            reservation = Reservation(
                **reservation_data.dict(),
                status="pending"
            )
            self.db.add(reservation)
            self.db.commit()
            self.db.refresh(reservation)
            
            # Generate friendly message about alternatives with priority-based suggestions
            if len(alternatives) == 1:
                alt = alternatives[0]
                if alt.capacity == 2 and reservation_data.party_size == 4:
                    message = f"I don't have a 4-seater available in your preferred section, but I can offer you two combined 2-seater tables in our {alt.section.name} section. Would that work for you?"
                else:
                    message = f"I don't have a {reservation_data.party_size}-seater available in your preferred section, but I can offer you a {alt.capacity}-seater in our {alt.section.name} section. Would that work for you?"
            else:
                alt_descriptions = []
                for alt in alternatives:
                    if alt.capacity == 2 and reservation_data.party_size == 4:
                        alt_descriptions.append(f"two combined 2-seater tables in {alt.section.name}")
                    else:
                        alt_descriptions.append(f"a {alt.capacity}-seater in {alt.section.name}")
                
                alt_text = ", ".join(alt_descriptions)
                message = f"I don't have a {reservation_data.party_size}-seater available in your preferred section, but I have these alternatives: {alt_text}. Which would you prefer?"
            
            return False, message, reservation, alternatives
        
        # No alternatives available
        return False, "I'm sorry, but we don't have any tables available for your party size at that time. Would you like to try a different time or date?", None, []
    
    def get_available_times(self, date: datetime, party_size: int, 
                           section_preference: Optional[str] = None) -> List[str]:
        """Get available reservation times for a given date and party size"""
        # Restaurant hours (configurable)
        start_time = datetime.strptime("11:00", "%H:%M").time()
        end_time = datetime.strptime("22:00", "%H:%M").time()
        
        available_times = []
        current_time = start_time
        
        while current_time <= end_time:
            time_str = current_time.strftime("%H:%M")
            
            # Check if any table is available at this time
            table = self.find_available_table(party_size, date, time_str, section_preference)
            if table:
                available_times.append(time_str)
            
            # Move to next 30-minute slot
            current_time = (datetime.combine(datetime.today(), current_time) + 
                          timedelta(minutes=30)).time()
        
        return available_times
    
    def cancel_reservation(self, reservation_id: int) -> bool:
        """Cancel a reservation"""
        reservation = self.db.query(Reservation).filter(
            Reservation.id == reservation_id
        ).first()
        
        if reservation:
            reservation.status = "cancelled"
            self.db.commit()
            return True
        
        return False
    
    def _is_table_available(self, table_id: int, date: datetime, time: str) -> bool:
        """Check if a specific table is available at the given time"""
        # Check for existing reservations for this table at the same time
        existing_reservation = self.db.query(Reservation).filter(
            and_(
                Reservation.table_id == table_id,
                Reservation.reservation_date == date,
                Reservation.reservation_time == time,
                Reservation.status.in_(["confirmed", "pending", "active"])
            )
        ).first()
        
        return existing_reservation is None
    
    def _is_time_slot_full(self, date: datetime, time: str) -> bool:
        """Check if a time slot is completely booked (no tables available)"""
        # Get all active tables
        total_tables = self.db.query(Table).filter(Table.is_active == True).count()
        
        # Get all confirmed/pending reservations for this time slot
        booked_tables = self.db.query(Reservation).filter(
            and_(
                Reservation.reservation_date == date,
                Reservation.reservation_time == time,
                Reservation.status.in_(["confirmed", "pending", "active"]),
                Reservation.table_id.isnot(None)  # Only count reservations with assigned tables
            )
        ).count()
        
        # If all tables are booked, the time slot is full
        return booked_tables >= total_tables
    
    def _get_booked_table_ids(self, date: datetime, time: str) -> List[int]:
        """Get list of booked table IDs for a specific date and time"""
        existing_reservations = self.db.query(Reservation).filter(
            and_(
                Reservation.reservation_date == date,
                Reservation.reservation_time == time,
                Reservation.status.in_(["confirmed", "pending", "active"])
            )
        ).all()
        
        return [r.table_id for r in existing_reservations if r.table_id]
    
    def _find_private_table(self, booked_table_ids: List[int]) -> Optional[Table]:
        """Find available private area table (Table 22)"""
        return self.db.query(Table).filter(
            and_(
                Table.is_active == True,
                Table.table_number == "22",  # Private area table
                ~Table.id.in_(booked_table_ids) if booked_table_ids else True
            )
        ).first()
    
    def _find_exact_capacity_table(self, party_size: int, booked_table_ids: List[int], 
                                 section_preference: Optional[str] = None) -> Optional[Table]:
        """Find table with exact capacity match, following priority order"""
        # Get sections in priority order (Lake View -> Garden View -> Indoors)
        sections_query = self.db.query(RestaurantSection).filter(
            RestaurantSection.is_active == True
        ).order_by(RestaurantSection.priority)
        
        if section_preference and section_preference.lower() != "any":
            sections_query = sections_query.filter(
                RestaurantSection.name.ilike(f"%{section_preference}%")
            )
        
        sections = sections_query.all()
        
        for section in sections:
            table = self.db.query(Table).filter(
                and_(
                    Table.is_active == True,
                    Table.capacity == party_size,
                    Table.section_id == section.id,
                    ~Table.id.in_(booked_table_ids) if booked_table_ids else True
                )
            ).first()
            
            if table:
                return table
        
        return None
    
    def _find_table_combination_for_4(self, booked_table_ids: List[int], 
                                    section_preference: Optional[str] = None) -> Optional[List[Table]]:
        """Find two 2-seater tables that can be combined for 4 people"""
        # Get sections in priority order
        sections_query = self.db.query(RestaurantSection).filter(
            and_(
                RestaurantSection.is_active == True,
                RestaurantSection.can_combine_tables == True
            )
        ).order_by(RestaurantSection.priority)
        
        if section_preference and section_preference.lower() != "any":
            sections_query = sections_query.filter(
                RestaurantSection.name.ilike(f"%{section_preference}%")
            )
        
        sections = sections_query.all()
        
        for section in sections:
            # Find two available 2-seater tables in this section
            available_2_seaters = self.db.query(Table).filter(
                and_(
                    Table.is_active == True,
                    Table.capacity == 2,
                    Table.section_id == section.id,
                    ~Table.id.in_(booked_table_ids) if booked_table_ids else True
                )
            ).limit(2).all()
            
            if len(available_2_seaters) >= 2:
                return available_2_seaters
        
        return None
    
    def _find_larger_table(self, party_size: int, booked_table_ids: List[int], 
                          section_preference: Optional[str] = None) -> Optional[Table]:
        """Find a larger table that can accommodate the party"""
        # Get sections in priority order
        sections_query = self.db.query(RestaurantSection).filter(
            RestaurantSection.is_active == True
        ).order_by(RestaurantSection.priority)
        
        if section_preference and section_preference.lower() != "any":
            sections_query = sections_query.filter(
                RestaurantSection.name.ilike(f"%{section_preference}%")
            )
        
        sections = sections_query.all()
        
        for section in sections:
            table = self.db.query(Table).filter(
                and_(
                    Table.is_active == True,
                    Table.capacity > party_size,
                    Table.section_id == section.id,
                    ~Table.id.in_(booked_table_ids) if booked_table_ids else True
                )
            ).order_by(Table.capacity).first()  # Get smallest larger table
            
            if table:
                return table
        
        return None
