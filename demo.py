#!/usr/bin/env python3
"""
Demo script for Lakeview Gardens Restaurant Reservation Manager
"""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

def test_health():
    """Test the health endpoint"""
    print("🏥 Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/health")
        if response.status_code == 200:
            print("✅ Health check passed")
            return True
        else:
            print("❌ Health check failed")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure it's running on http://localhost:8000")
        return False

def test_faq_system():
    """Test the FAQ system"""
    print("\n🤖 Testing FAQ system...")
    
    questions = [
        "What are your opening hours?",
        "Do you have vegetarian options?",
        "What's your cancellation policy?",
        "Can I bring my own wine?",
        "What are your signature dishes?"
    ]
    
    for question in questions:
        print(f"\nQ: {question}")
        try:
            response = requests.post(f"{BASE_URL}/api/faq", 
                                  json={"question": question})
            if response.status_code == 200:
                result = response.json()
                print(f"A: {result['answer']}")
            else:
                print("❌ Failed to get answer")
        except Exception as e:
            print(f"❌ Error: {e}")

def test_reservation_system():
    """Test the reservation system"""
    print("\n📅 Testing reservation system...")
    
    # Test natural language reservation
    print("\n💬 Testing natural language reservation...")
    natural_request = {
        "text": "I need a table for 4 people at 7 PM tomorrow in the garden view",
        "email": "demo@example.com",
        "phone": "555-1234"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/reservations/natural", 
                              json=natural_request)
        if response.status_code == 200:
            result = response.json()
            print(f"Response: {result['message']}")
            if result['success']:
                print("✅ Natural language reservation successful!")
            else:
                print("💡 Reservation needs alternatives")
        else:
            print("❌ Failed to process natural language request")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test traditional form reservation
    print("\n📝 Testing traditional form reservation...")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    form_data = {
        "customer_name": "Demo Customer",
        "customer_email": "demo@example.com",
        "customer_phone": "555-1234",
        "party_size": 2,
        "reservation_date": tomorrow,
        "reservation_time": "19:00",
        "section_preference": "lake view",
        "special_requests": "Window seat if possible"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/reservations", 
                              json=form_data)
        if response.status_code == 200:
            result = response.json()
            print(f"Response: {result['message']}")
            if result['success']:
                print("✅ Traditional reservation successful!")
            else:
                print("💡 Reservation needs alternatives")
        else:
            print("❌ Failed to create traditional reservation")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_available_times():
    """Test available times endpoint"""
    print("\n🕐 Testing available times...")
    
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    try:
        response = requests.get(f"{BASE_URL}/api/available-times", 
                              params={"date": tomorrow, "party_size": 4})
        if response.status_code == 200:
            result = response.json()
            print(f"Available times for 4 people on {tomorrow}:")
            for time in result['available_times'][:5]:  # Show first 5 times
                print(f"  - {time}")
        else:
            print("❌ Failed to get available times")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_restaurant_info():
    """Test restaurant information endpoints"""
    print("\n🏪 Testing restaurant information...")
    
    # Test sections
    try:
        response = requests.get(f"{BASE_URL}/api/sections")
        if response.status_code == 200:
            sections = response.json()
            print("Restaurant sections:")
            for section in sections:
                print(f"  - {section['name']}: {section['description']}")
        else:
            print("❌ Failed to get sections")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test tables
    try:
        response = requests.get(f"{BASE_URL}/api/tables")
        if response.status_code == 200:
            tables = response.json()
            print(f"\nTotal tables: {len(tables)}")
            
            # Group by capacity
            capacity_groups = {}
            for table in tables:
                cap = table['capacity']
                if cap not in capacity_groups:
                    capacity_groups[cap] = 0
                capacity_groups[cap] += 1
            
            for capacity, count in sorted(capacity_groups.items()):
                print(f"  - {capacity}-seater tables: {count}")
        else:
            print("❌ Failed to get tables")
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Main demo function"""
    print("🏞️ Lakeview Gardens Restaurant Reservation Manager - Demo")
    print("=" * 70)
    
    # Test health first
    if not test_health():
        return
    
    # Run all tests
    test_faq_system()
    test_reservation_system()
    test_available_times()
    test_restaurant_info()
    
    print("\n🎉 Demo completed!")
    print("\n🌐 Open your browser to http://localhost:8000 to see the full interface")
    print("📚 Check the API documentation at http://localhost:8000/docs")

if __name__ == "__main__":
    main()
