#!/usr/bin/env python3
"""
Test script to verify double-booking prevention
"""

import requests
import json
from datetime import datetime, timedelta

def test_double_booking():
    """Test if double-booking is prevented"""
    base_url = "http://localhost:8000"
    
    # Test data
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    test_time = "20:30"
    
    print("🧪 Testing Double-Booking Prevention")
    print("=" * 50)
    
    # Test 1: Make first reservation
    print(f"\n📅 Test 1: Making first reservation for {tomorrow} at {test_time}")
    reservation1 = {
        "text": f"I need a table for 2 people at {test_time} tomorrow in the lake view",
        "email": "test1@example.com",
        "phone": "123-456-7890"
    }
    
    try:
        response1 = requests.post(f"{base_url}/api/reservations/natural", json=reservation1)
        result1 = response1.json()
        
        if result1.get("success"):
            print(f"✅ First reservation successful: {result1['message']}")
        else:
            print(f"❌ First reservation failed: {result1['message']}")
            return False
    except Exception as e:
        print(f"❌ Error making first reservation: {e}")
        return False
    
    # Test 2: Try to make second reservation for same time
    print(f"\n📅 Test 2: Trying to make second reservation for {tomorrow} at {test_time}")
    reservation2 = {
        "text": f"I need a table for 2 people at {test_time} tomorrow in the lake view",
        "email": "test2@example.com",
        "phone": "987-654-3210"
    }
    
    try:
        response2 = requests.post(f"{base_url}/api/reservations/natural", json=reservation2)
        result2 = response2.json()
        
        if not result2.get("success"):
            print(f"✅ Double-booking prevented: {result2['message']}")
            return True
        else:
            print(f"❌ Double-booking allowed: {result2['message']}")
            return False
    except Exception as e:
        print(f"❌ Error making second reservation: {e}")
        return False

def check_reservations():
    """Check current reservations"""
    base_url = "http://localhost:8000"
    
    print("\n📊 Checking Current Reservations")
    print("=" * 40)
    
    try:
        response = requests.get(f"{base_url}/api/admin/reservations")
        result = response.json()
        
        print(f"Total Reservations: {result['total_reservations']}")
        
        if result['reservations']:
            print("\nRecent Reservations:")
            for res in result['reservations'][:5]:  # Show last 5
                print(f"  • {res['customer_name']} - {res['party_size']} people - {res['date']} {res['time']} - {res['table_number']} ({res['section_name']}) - {res['status']}")
        else:
            print("No reservations found.")
            
    except Exception as e:
        print(f"❌ Error checking reservations: {e}")

if __name__ == "__main__":
    print("🏞️ Lakeview Gardens - Double-Booking Test")
    print("Make sure the server is running on localhost:8000")
    print()
    
    # Check current reservations
    check_reservations()
    
    # Test double-booking prevention
    success = test_double_booking()
    
    if success:
        print("\n🎉 Double-booking prevention test PASSED!")
    else:
        print("\n💥 Double-booking prevention test FAILED!")
    
    # Check reservations again
    check_reservations()
