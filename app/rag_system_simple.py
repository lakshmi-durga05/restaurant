"""
Simple fallback RAG system used when the full stack is unavailable.
This file ensures imports in app/main.py always succeed.
"""
from __future__ import annotations

class SimpleRestaurantRAGSystem:
    def __init__(self) -> None:
        pass

    def answer_question(self, question: str) -> tuple[str, float]:
        q = (question or "").lower()
        # Deterministic, safe answers for common FAQs
        if any(k in q for k in ["address", "location", "where are you", "reach"]):
            return (
                "Our address is Lakeview Gardens, 123 Lakeside Road, Green Park, Hyderabad 500001. "
                "We are 2 km from Green Park Metro and have on-site parking.",
                0.9,
            )
        if any(k in q for k in ["contact", "phone", "mobile", "email"]):
            return (
                "Phone: +91-98765-43210, Email: reservations@lakeviewgardens.example.",
                0.9,
            )
        if any(k in q for k in ["special", "signature", "dish", "menu"]):
            return (
                "Signature dishes: Lake View Lobster Risotto, Garden Herb-Crusted Rack of Lamb, "
                "Smoked Paneer Tikka (veg), and Chocolate Lava Cake.",
                0.8,
            )
        if any(k in q for k in ["hours", "timing", "open", "close"]):
            return (
                "We are open daily from 11:00 AM to 11:00 PM. The kitchen closes at 10:30 PM.",
                0.8,
            )
        return (
            "I can help with bookings, availability, address/contact, policies, and specials."
            " Ask me about a date/time/view and I can proceed to book.",
            0.6,
        )
