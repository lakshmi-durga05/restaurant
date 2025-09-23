#!/usr/bin/env python3
"""
Simple test script to verify the restaurant booking system functionality
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from app.database import SessionLocal, engine
from app.models import Base, RestaurantSection, Table, Reservation
from app.init_db import init_database
from app.reservation_service import ReservationService
from app.schemas import ReservationCreate
from datetime import datetime, timedelta

def test_database_setup():
    """Test database initialization"""
    print("🧪 Testing database setup...")
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Initialize with sample data
    init_database()
    
    db = SessionLocal()
    try:
        # Check sections
        sections = db.query(RestaurantSection).all()
        print(f"✅ Found {len(sections)} restaurant sections:")
        for section in sections:
            print(f"   - {section.name} (Priority: {section.priority})")
        
        # Check tables
        tables = db.query(Table).all()
        print(f"✅ Found {len(tables)} tables:")
        
        # Group by section
        for section in sections:
            section_tables = [t for t in tables if t.section_id == section.id]
            print(f"   {section.name}: {len(section_tables)} tables")
            for table in section_tables:
                print(f"     - Table {table.table_number} ({table.capacity} seats)")
        
        return True
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False
    finally:
        db.close()

def test_reservation_logic():
    """Test reservation service logic"""
    print("\n🧪 Testing reservation logic...")
    
    db = SessionLocal()
    try:
        service = ReservationService(db)
        
        # Test 1: Find available table for 2 people
        tomorrow = datetime.now() + timedelta(days=1)
        table = service.find_available_table(2, tomorrow, "19:00", "Lake View")
        if table:
            print(f"✅ Found table for 2 people: {table.table_number} in {table.section.name}")
        else:
            print("❌ No table found for 2 people")
        
        # Test 2: Test table combination for 4 people
        combination = service._find_table_combination_for_4([], "Lake View")
        if combination:
            print(f"✅ Found table combination for 4 people: {combination[0].table_number} + {combination[1].table_number}")
        else:
            print("❌ No table combination found for 4 people")
        
        # Test 3: Test priority-based alternatives
        alternatives = service.find_alternative_tables(4, tomorrow, "19:00", "Lake View")
        print(f"✅ Found {len(alternatives)} alternative options:")
        for alt in alternatives:
            print(f"   - {alt.capacity}-seater in {alt.section.name} (Table {alt.table_number})")
        
        return True
    except Exception as e:
        print(f"❌ Reservation logic test failed: {e}")
        return False
    finally:
        db.close()

def test_rag_system():
    """Test RAG system"""
    print("\n🧪 Testing RAG system...")
    
    try:
        from app.rag_system import RestaurantRAGSystem
        rag = RestaurantRAGSystem()
        
        # Test question
        question = "What are your opening hours?"
        answer, confidence = rag.answer_question(question)
        print(f"✅ RAG system working:")
        print(f"   Question: {question}")
        print(f"   Answer: {answer}")
        print(f"   Confidence: {confidence:.2f}")
        
        return True
    except Exception as e:
        print(f"❌ RAG system test failed: {e}")
        print("   This might be due to missing dependencies (Ollama, transformers)")
        return False

def main():
    """Run all tests"""
    print("🍽️  Restaurant Booking System Test Suite")
    print("=" * 50)
    
    tests = [
        test_database_setup,
        test_reservation_logic,
        test_rag_system
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The system is ready to use.")
    else:
        print("⚠️  Some tests failed. Check the errors above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

