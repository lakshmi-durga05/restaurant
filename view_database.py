#!/usr/bin/env python3
"""
Simple database viewer for Lakeview Gardens Restaurant
Shows all customers, reservations, and tables
"""

import sqlite3
import os
from datetime import datetime

def view_database():
    """View all database contents"""
    db_path = "restaurant_booking.db"
    
    if not os.path.exists(db_path):
        print("❌ Database not found. Please run the application first.")
        return
    
    print("🏞️ Lakeview Gardens Restaurant - Database Viewer")
    print("=" * 60)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # View Restaurant Sections
        print("\n📍 RESTAURANT SECTIONS:")
        print("-" * 30)
        cursor.execute("SELECT * FROM restaurant_sections")
        sections = cursor.fetchall()
        for section in sections:
            print(f"ID: {section[0]}, Name: {section[1]}, Description: {section[2]}, Active: {section[3]}")
        
        # View Tables
        print("\n🪑 TABLES:")
        print("-" * 30)
        cursor.execute("""
            SELECT t.id, t.table_number, t.capacity, s.name as section_name, t.is_active
            FROM tables t
            JOIN restaurant_sections s ON t.section_id = s.id
            ORDER BY s.name, t.capacity
        """)
        tables = cursor.fetchall()
        for table in tables:
            print(f"ID: {table[0]}, Table: {table[1]}, Capacity: {table[2]}, Section: {table[3]}, Active: {table[4]}")
        
        # View Reservations
        print("\n📅 RESERVATIONS:")
        print("-" * 30)
        cursor.execute("""
            SELECT r.id, r.customer_name, r.customer_email, r.party_size, 
                   r.reservation_date, r.reservation_time, r.status, r.created_at,
                   t.table_number, s.name as section_name
            FROM reservations r
            LEFT JOIN tables t ON r.table_id = t.id
            LEFT JOIN restaurant_sections s ON t.section_id = s.id
            ORDER BY r.created_at DESC
        """)
        reservations = cursor.fetchall()
        
        if reservations:
            print(f"{'ID':<3} {'Name':<15} {'Email':<25} {'Party':<5} {'Date':<12} {'Time':<8} {'Status':<10} {'Table':<8} {'Section':<12}")
            print("-" * 100)
            for res in reservations:
                print(f"{res[0]:<3} {res[1]:<15} {res[2]:<25} {res[3]:<5} {res[4]:<12} {res[5]:<8} {res[6]:<10} {res[7]:<8} {res[8]:<12}")
        else:
            print("No reservations found.")
        
        # Summary
        print("\n📊 SUMMARY:")
        print("-" * 30)
        cursor.execute("SELECT COUNT(*) FROM reservations")
        total_reservations = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM reservations WHERE status = 'confirmed'")
        confirmed_reservations = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM reservations WHERE status = 'pending'")
        pending_reservations = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM reservations WHERE status = 'cancelled'")
        cancelled_reservations = cursor.fetchone()[0]
        
        print(f"Total Reservations: {total_reservations}")
        print(f"Confirmed: {confirmed_reservations}")
        print(f"Pending: {pending_reservations}")
        print(f"Cancelled: {cancelled_reservations}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error viewing database: {e}")

if __name__ == "__main__":
    view_database()
