from pydantic import BaseModel, EmailStr, Field, validator
from typing import List, Optional
from datetime import datetime
from enum import Enum

from pydantic import ConfigDict, field_validator


class Feature(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class TableBase(BaseModel):
    capacity: int = Field(..., gt=0, le=12, description="Number of people the table can accommodate")
    view: str = Field(..., description="Type of view (window, garden, private, etc.)")
    is_available: bool = True

class TableCreate(TableBase):
    pass

class Table(TableBase):
    id: int
    features: List[Feature] = []

    model_config = ConfigDict(from_attributes=True)

class ReservationBase(BaseModel):
    customer_name: str = Field(..., min_length=2, max_length=100)
    customer_email: EmailStr
    customer_phone: str = Field(..., pattern=r'^\+?[1-9]\d{6,14}$')  # E.164 format (min 7 digits)
    reservation_time: datetime
    party_size: int = Field(..., gt=0, le=12, description="Number of people in the party")
    preferred_view: Optional[str] = None
    special_requests: Optional[str] = None

    @field_validator('reservation_time')
    @classmethod
    def validate_future_date(cls, v: datetime) -> datetime:
        if v < datetime.now():
            raise ValueError("Reservation time must be in the future")
        return v

class ReservationCreate(ReservationBase):
    table_id: Optional[int] = None
    items: Optional[list[dict]] = None  # [{"menu_item_id": int, "quantity": int}]

class Reservation(ReservationBase):
    id: int
    table_id: int
    status: str
    created_at: datetime
    items: Optional[list[dict]] = None

    model_config = ConfigDict(from_attributes=True)

class ReservationUpdate(BaseModel):
    customer_name: Optional[str] = None
    customer_email: Optional[EmailStr] = None
    customer_phone: Optional[str] = None
    reservation_time: Optional[datetime] = None
    party_size: Optional[int] = None
    status: Optional[str] = None
    special_requests: Optional[str] = None

class TableAvailabilityCheck(BaseModel):
    party_size: int = Field(..., gt=0, le=12)
    reservation_time: datetime
    preferred_view: Optional[str] = None

    @field_validator('reservation_time')
    @classmethod
    def validate_future_date(cls, v: datetime) -> datetime:
        if v < datetime.now():
            raise ValueError("Reservation time must be in the future")
        return v

class TableSuggestion(BaseModel):
    tables: List[Table]
    total_capacity: int
    is_exact_match: bool
    message: str
    other_view_suggestions: Optional[List[Table]] = None
    note: Optional[str] = None

class ReservationResponse(BaseModel):
    success: bool
    message: str
    reservation: Optional[Reservation] = None
    suggestions: Optional[TableSuggestion] = None


# Menu schemas
class MenuItem(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: float
    is_special: bool

    model_config = ConfigDict(from_attributes=True)


class ReservationItem(BaseModel):
    menu_item_id: int
    quantity: int = 1
