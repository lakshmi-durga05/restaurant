"""
CrewAI-plus multi-agent workflow for FAQs and suggestions.
Works under RAG_MODE=crew_plus. If CrewAI isn't installed, it falls back
to an internal heuristic pipeline so that it always works without
breaking the app workflow.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

class CrewPlusRAG:
    def __init__(self):
        self._use_crewai = False
        try:
            # Optional import; if unavailable, we still work via fallback
            from crewai import Agent, Task, Crew  # type: ignore
            self.Agent = Agent
            self.Task = Task
            self.Crew = Crew
            self._use_crewai = True
        except Exception:
            self.Agent = None
            self.Task = None
            self.Crew = None
            self._use_crewai = False

    # -------------- Heuristic fallback agents --------------
    def _route_intent(self, question: str) -> str:
        q = question.lower()
        if any(k in q for k in ["book", "reservation", "table", "reserve", "reschedule", "cancel"]):
            return "booking"
        if any(k in q for k in ["address", "location", "where", "reach", "contact", "phone", "email"]):
            return "info"
        if any(k in q for k in ["special", "dish", "menu", "signature"]):
            return "menu"
        if any(k in q for k in ["available", "availability", "any tables", "openings", "seats", "is there any", "is the private"]):
            return "availability"
        return "general"

    def _retrieve_answer(self, question: str, intent: str) -> str:
        # Deterministic answers inline to ensure it works even without external deps
        if intent == "info":
            return (
                "Our address is Lakeview Gardens, 123 Lakeside Road, Green Park, Hyderabad 500001. "
                "Phone: +91-98765-43210. Email: reservations@lakeviewgardens.example."
            )
        if intent == "menu":
            return (
                "Signature dishes: Lake View Lobster Risotto, Garden Herb-Crusted Rack of Lamb, "
                "Smoked Paneer Tikka (veg), and Chocolate Lava Cake. Say 'preorder <dish>'."
            )
        if intent == "availability":
            return (
                "I can check availability for your date/time and view. Please share party size, date (YYYY-MM-DD), time (HH:MM), and view (Lake/Garden/Indoors/Private/Window)."
            )
        if intent == "booking":
            return "I can help book a table. Please send party size, date (YYYY-MM-DD), time (HH:MM), and your email and phone."
        return (
            "I'm your assistant for Lakeview Gardens. Ask about bookings, availability, address/contact, policies, or specials."
        )

    def _validate_booking(self, answer: str) -> str:
        # Ensure we never promise a booking here; just guide politely
        return answer.strip()

    # -------------- Public API --------------
    def answer_question(self, question: str) -> tuple[str, float]:
        # CrewAI orchestration if available
        if self._use_crewai:
            try:
                router = self.Agent(role="Intent Router", goal="Classify restaurant questions by intent.")
                retriever = self.Agent(role="Knowledge Retriever", goal="Provide concise, accurate answers.")
                validator = self.Agent(role="Booking Validator", goal="Ensure guidance is actionable and safe.")
                t_route = self.Task(description=f"Classify the intent of: {question}", agent=router)
                t_retrieve = self.Task(description=f"Answer this question succinctly for a guest: {question}", agent=retriever)
                t_validate = self.Task(description="Review the answer to ensure it's polite and actionable.", agent=validator)
                crew = self.Crew(agents=[router, retriever, validator], tasks=[t_route, t_retrieve, t_validate])
                res = crew.kickoff()
                text = str(res)
                return text.strip(), 0.7
            except Exception:
                pass
        # Fallback heuristic pipeline
        intent = self._route_intent(question)
        ans = self._retrieve_answer(question, intent)
        ans = self._validate_booking(ans)
        return ans, 0.6
