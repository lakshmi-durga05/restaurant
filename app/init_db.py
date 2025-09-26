from sqlalchemy.orm import Session
from .database import SessionLocal, engine
from .models import Base, RestaurantSection, Table

def init_database():
    """Initialize database with restaurant sections and tables"""
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Check if data already exists
        if db.query(RestaurantSection).first():
            print("Database already initialized. Skipping...")
            return
        
            # Create restaurant sections with priority order (lower number = higher priority)
        sections = [
            RestaurantSection(
                name="Lake View",
                description="Breathtaking views of the lake with elegant outdoor and indoor seating options.",
                priority=1,  # Highest priority
                max_2_seaters=2,
                max_4_seaters=2,
                max_12_seaters=2,
                max_30_seaters=0,
                can_combine_tables=True
            ),
            RestaurantSection(
                name="Garden View",
                description="Peaceful garden setting with fresh air and natural beauty.",
                priority=2,  # Second priority
                max_2_seaters=2,
                max_4_seaters=2,
                max_12_seaters=2,
                max_30_seaters=0,
                can_combine_tables=True
            ),
            RestaurantSection(
                name="Indoors",
                description="Comfortable indoor dining with classic restaurant ambiance.",
                priority=3,  # Third priority
                max_2_seaters=4,
                max_4_seaters=2,
                max_12_seaters=1,
                max_30_seaters=0,
                can_combine_tables=True
            ),
            RestaurantSection(
                name="Private Area",
                description="Exclusive private dining area for large groups and special occasions.",
                priority=4,  # Special priority (separate from others)
                max_2_seaters=0,
                max_4_seaters=0,
                max_12_seaters=0,
                max_30_seaters=1,
                can_combine_tables=False
            )
        ]
        
        for section in sections:
            db.add(section)
        
        db.commit()
        
        # Get section IDs for table creation
        lake_view = db.query(RestaurantSection).filter_by(name="Lake View").first()
        garden_view = db.query(RestaurantSection).filter_by(name="Garden View").first()
        indoors = db.query(RestaurantSection).filter_by(name="Indoors").first()
        private_area = db.query(RestaurantSection).filter_by(name="Private Area").first()
        
        # Create tables for each section based on the floor plan
        tables = []
        
        # Lake View tables (Tables 10-15): 2*2 seaters, 2*4 seaters, 2*12 seaters
        tables.extend([
            Table(table_number="10", capacity=12, section_id=lake_view.id),  # Large rectangular table
            Table(table_number="11", capacity=12, section_id=lake_view.id),  # Large rectangular table
            Table(table_number="12", capacity=4, section_id=lake_view.id),   # Square table
            Table(table_number="13", capacity=4, section_id=lake_view.id),   # Square table
            Table(table_number="14", capacity=2, section_id=lake_view.id),   # Small rectangular table
            Table(table_number="15", capacity=2, section_id=lake_view.id),   # Small rectangular table
        ])
        
        # Indoors tables (Tables 1-9): 4*2 seaters, 2*4 seaters, 1*12 seater
        tables.extend([
            Table(table_number="1", capacity=12, section_id=indoors.id),     # Large rectangular table
            Table(table_number="2", capacity=2, section_id=indoors.id),      # Small rectangular table
            Table(table_number="3", capacity=2, section_id=indoors.id),      # Small rectangular table
            Table(table_number="4", capacity=4, section_id=indoors.id),      # Square table
            Table(table_number="5", capacity=4, section_id=indoors.id),      # Square table
            Table(table_number="6", capacity=2, section_id=indoors.id),      # Small rectangular table
            Table(table_number="7", capacity=2, section_id=indoors.id),      # Small rectangular table
            Table(table_number="8", capacity=2, section_id=indoors.id),      # Small rectangular table
            Table(table_number="9", capacity=2, section_id=indoors.id),      # Small rectangular table
        ])
        
        # Garden View tables (Tables 16-21): Same as Lake View
        tables.extend([
            Table(table_number="16", capacity=12, section_id=garden_view.id), # Large rectangular table
            Table(table_number="17", capacity=12, section_id=garden_view.id), # Large rectangular table
            Table(table_number="18", capacity=4, section_id=garden_view.id),  # Square table
            Table(table_number="19", capacity=4, section_id=garden_view.id),  # Square table
            Table(table_number="20", capacity=2, section_id=garden_view.id),  # Small rectangular table
            Table(table_number="21", capacity=2, section_id=garden_view.id),  # Small rectangular table
        ])
        
        # Private Area table (Table 22): 1*30 seater
        tables.extend([
            Table(table_number="22", capacity=30, section_id=private_area.id), # U-shaped table
        ])
        
        for table in tables:
            db.add(table)
        
        db.commit()
        
        print("✅ Database initialized successfully!")
        print(f"   - Created {len(sections)} restaurant sections")
        print(f"   - Created {len(tables)} tables")
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_database()
