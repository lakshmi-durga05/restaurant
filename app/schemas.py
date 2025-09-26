from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List

class RestaurantSectionBase(BaseModel):
    name: str
    description: Optional[str] = None

class RestaurantSectionCreate(RestaurantSectionBase):
    pass

class RestaurantSection(RestaurantSectionBase):
    id: int
    is_active: bool
    
    class Config:
        from_attributes = True

class TableBase(BaseModel):
    table_number: str
    capacity: int
    section_id: int

class TableCreate(TableBase):
    pass

class Table(TableBase):
    id: int
    is_active: bool
    section: RestaurantSection
    
    class Config:
        from_attributes = True

class ReservationBase(BaseModel):
    customer_name: str = "Guest"
    customer_email: str
    customer_phone: Optional[str] = None
    party_size: int
    reservation_date: datetime
    reservation_time: str
    section_preference: Optional[str] = None
    special_requests: Optional[str] = None

class ReservationCreate(ReservationBase):
    pass

class Reservation(ReservationBase):
    id: int
    table_id: Optional[int] = None
    status: str
    created_at: datetime
    table: Optional[Table] = None
    
    class Config:
        from_attributes = True

class ReservationResponse(BaseModel):
    success: bool
    message: str
    reservation: Optional[Reservation] = None
    alternatives: Optional[List[Table]] = None

class FAQQuery(BaseModel):
    question: str

class FAQResponse(BaseModel):
    answer: str
    confidence: float
