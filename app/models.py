from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Table, text, Float, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from .database import Base, engine, SessionLocal

# Association table for many-to-many relationship between tables and features
table_features = Table(
    'table_features',
    Base.metadata,
    Column('table_id', Integer, ForeignKey('tables.id')),
    Column('feature_id', Integer, ForeignKey('features.id'))
)

class Table(Base):
    __tablename__ = "tables"
    
    id = Column(Integer, primary_key=True, index=True)
    capacity = Column(Integer, nullable=False)
    view = Column(String(50), nullable=False)
    is_available = Column(Boolean, default=True)
    
    # Relationships
    reservations = relationship("Reservation", back_populates="table")
    features = relationship("Feature", secondary=table_features, back_populates="tables")

class Feature(Base):
    __tablename__ = "features"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    
    # Relationships
    tables = relationship("Table", secondary=table_features, back_populates="features")

class Reservation(Base):
    __tablename__ = "reservations"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String(100), nullable=False)
    customer_email = Column(String(100), nullable=False)
    customer_phone = Column(String(20), nullable=False)
    reservation_time = Column(DateTime, nullable=False)
    party_size = Column(Integer, nullable=False)
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=False)
    status = Column(String(20), default="confirmed")  # confirmed, cancelled, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    special_requests = Column(Text, nullable=True)
    
    # Relationships
    table = relationship("Table", back_populates="reservations")
    items = relationship("ReservationItem", back_populates="reservation", cascade="all, delete-orphan")


class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False, default=0.0)
    is_special = Column(Boolean, default=False)


class ReservationItem(Base):
    __tablename__ = "reservation_items"

    id = Column(Integer, primary_key=True, index=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=False)
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)

    reservation = relationship("Reservation", back_populates="items")
    menu_item = relationship("MenuItem")

def _sqlite_migrate_if_needed():
    """Perform lightweight migrations for SQLite if columns are missing."""
    # Create tables if not present
    Base.metadata.create_all(bind=engine)

    # Use a transaction so ALTERs are committed before any ORM queries
    with engine.begin() as conn:
        # Check columns of tables table
        result = conn.exec_driver_sql("PRAGMA table_info('tables')")
        columns = {row[1] for row in result}  # name is at index 1

        # Add missing columns
        if 'view' not in columns:
            conn.exec_driver_sql("ALTER TABLE tables ADD COLUMN view VARCHAR(50) NOT NULL DEFAULT 'window';")
        if 'is_available' not in columns:
            conn.exec_driver_sql("ALTER TABLE tables ADD COLUMN is_available BOOLEAN NOT NULL DEFAULT 1;")

        # Ensure reservations table has special_requests
        result_res = conn.exec_driver_sql("PRAGMA table_info('reservations')")
        res_cols = {row[1] for row in result_res}
        if 'special_requests' not in res_cols:
            conn.exec_driver_sql("ALTER TABLE reservations ADD COLUMN special_requests TEXT;")


def init_db():
    _sqlite_migrate_if_needed()

    db = SessionLocal()
    try:
        # Seed sample data only if no rows exist (raw SQL avoids selecting missing legacy columns)
        any_row = False
        try:
            any_row = db.execute(text("SELECT id FROM tables LIMIT 1")).first() is not None
        except Exception:
            any_row = False

        if not any_row:
            # Create features first (ensure unique names)
            feature_names = ["window", "garden", "private", "outdoor", "romantic", "lake"]
            features = {name: Feature(name=name) for name in feature_names}
            db.add_all(features.values())
            db.flush()

            # Sample tables
            tables = [
                Table(capacity=2, view="window", is_available=True, features=[features["window"]]),
                Table(capacity=2, view="garden", is_available=True, features=[features["garden"]]),
                Table(capacity=4, view="window", is_available=True, features=[features["window"]]),
                Table(capacity=4, view="garden", is_available=True, features=[features["garden"]]),
                Table(capacity=6, view="window", is_available=True, features=[features["window"], features["romantic"]]),
                Table(capacity=6, view="garden", is_available=True, features=[features["garden"], features["outdoor"]]),
                Table(capacity=8, view="private", is_available=True, features=[features["private"], features["romantic"]]),
                # Lake view tables
                Table(capacity=2, view="lake", is_available=True, features=[features["lake"], features["romantic"]]),
                Table(capacity=4, view="lake", is_available=True, features=[features["lake"]]),
                Table(capacity=6, view="lake", is_available=True, features=[features["lake"], features["outdoor"]]),
            ]
            db.add_all(tables)
            db.commit()
            print("✅ Database initialized with sample data")

        # Seed menu items if empty
        if not db.query(MenuItem).first():
            menu = [
                MenuItem(name="Grilled Lake Fish", description="Fresh catch with herbs", price=18.5, is_special=True),
                MenuItem(name="Serenity Butter Chicken", description="Creamy tomato gravy", price=14.0, is_special=True),
                MenuItem(name="Garden Fresh Salad", description="Mixed greens with vinaigrette", price=8.0, is_special=False),
                MenuItem(name="Woodfired Paneer Tikka", description="Smoky and spiced", price=12.0, is_special=True),
                MenuItem(name="Chocolate Lava Cake", description="Molten center dessert", price=7.5, is_special=False),
                # More mains & specials
                MenuItem(name="Tandoori Prawns", description="Char-grilled prawns with spices", price=19.0, is_special=True),
                MenuItem(name="Herb-Crusted Lamb Chops", description="Served with rosemary jus", price=22.0, is_special=True),
                MenuItem(name="Truffle Mushroom Risotto", description="Creamy arborio with truffle", price=16.0, is_special=False),
                MenuItem(name="Vegan Buddha Bowl", description="Quinoa, roasted veggies, tahini", price=13.5, is_special=False),
                MenuItem(name="Margherita Woodfired Pizza", description="Tomato, mozzarella, basil", price=11.0, is_special=False),
                MenuItem(name="Chefs Special Biryani", description="Fragrant basmati with saffron", price=15.0, is_special=True),
                MenuItem(name="Mango Lassi", description="Refreshing yogurt drink", price=5.0, is_special=False),
            ]
            db.add_all(menu)
            db.commit()

        # Ensure additional views exist on legacy DBs: lake, rooftop, patio
        def ensure_view(view_name: str, default_capacities=(2, 4, 6)):
            # Ensure feature exists
            feat = db.query(Feature).filter(Feature.name == view_name).first()
            if not feat:
                feat = Feature(name=view_name)
                db.add(feat)
                db.flush()
            # If no tables with this view, create defaults
            if db.query(Table).filter(Table.view == view_name).count() == 0:
                new_tables = [
                    Table(capacity=c, view=view_name, is_available=True, features=[feat])
                    for c in default_capacities
                ]
                db.add_all(new_tables)
                db.commit()

        # Ensure only 'lake' (do not recreate removed views rooftop/patio)
        for v in ("lake",):
            ensure_view(v)
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        db.rollback()
    finally:
        db.close()

# Initialize/upgrade DB on import
init_db()
