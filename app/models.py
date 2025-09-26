from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text, CheckConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class RestaurantSection(Base):
    """Restaurant sections: Lake View, Garden View, Indoors, Private"""
    __tablename__ = "restaurant_sections"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)  # Lake View, Garden View, Indoors, Private
    description = Column(Text)
    priority = Column(Integer, default=0)  # Lower number means higher priority
    is_active = Column(Boolean, default=True)
    
    # Section-specific configurations
    max_2_seaters = Column(Integer, default=0)
    max_4_seaters = Column(Integer, default=0)
    max_12_seaters = Column(Integer, default=0)
    max_30_seaters = Column(Integer, default=0)
    can_combine_tables = Column(Boolean, default=True)

class Table(Base):
    """Restaurant tables with different capacities"""
    __tablename__ = "tables"
    
    id = Column(Integer, primary_key=True, index=True)
    table_number = Column(String(10), unique=True, nullable=False)
    capacity = Column(Integer, nullable=False)  # 2, 4, 12, 30
    section_id = Column(Integer, ForeignKey("restaurant_sections.id"))
    is_active = Column(Boolean, default=True)
    is_combined = Column(Boolean, default=False)  # If this table is part of a combined table
    combined_with = Column(String(100), nullable=True)  # Comma-separated list of table numbers combined
    
    section = relationship("RestaurantSection", back_populates="tables")
    reservations = relationship("Reservation", back_populates="table")

class Reservation(Base):
    """Customer reservations"""
    __tablename__ = "reservations"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String(100), nullable=False)
    customer_email = Column(String(100), nullable=False)
    customer_phone = Column(String(20))
    party_size = Column(Integer, nullable=False)
    reservation_date = Column(DateTime, nullable=False)
    reservation_time = Column(String(5), nullable=False)  # HH:MM format
    duration = Column(Integer, default=90)  # Duration in minutes
    section_preference = Column(String(50))  # Lake View, Garden View, Indoors, Private, or Any
    table_id = Column(Integer, ForeignKey("tables.id"))
    status = Column(String(20), default="confirmed")  # confirmed, cancelled, completed, no-show
    special_requests = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    table = relationship("Table", back_populates="reservations")
    
    # Note: Double-booking prevention is handled at the application level
    # in the reservation service to maintain compatibility with SQLite

# Back-populate relationships
RestaurantSection.tables = relationship("Table", back_populates="section")
