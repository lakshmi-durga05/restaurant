from __future__ import annotations
from typing import Optional

from .config import settings
from . import reservation_service
from .llm import ask_ollama


def _build_world_state(db) -> str:
    """Assemble structured context the agent can use to answer arbitrary questions.
    This does not require any external agent framework and works even if optional
    packages are missing. If USE_OLLAMA is enabled, the reasoning call will be
    executed via the local model.
    """
    try:
        views = reservation_service.get_all_views(db)
    except Exception:
        views = []

    # Per-view small snapshot
    lines = []
    for v in views[:6]:
        try:
            s = reservation_service.view_stats(db, v)
            lines.append(f"- {v}: total {s['total']}, booked {s['booked']}, available {s['available']}")
        except Exception:
            continue

    try:
        today_bookings = reservation_service.count_bookings_today(db)
        people_today = reservation_service.count_people_booked_today(db) if hasattr(reservation_service, 'count_people_booked_today') else None
    except Exception:
        today_bookings = None
        people_today = None

    context = [
        "Facts:",
        "Hours: open daily 12:00–23:00; last seating 22:00; Lunch 12:00–15:30; Dinner 18:30–23:00.",
        "Address: 123 Serene Lake Drive, Lakeside District, Bangalore 560001, India.",
        "Contact: +91 98765 43210 | reservations@lake-serinity.example",
        "Views available: " + (", ".join(views) if views else "window, garden, private, lake"),
        "Availability snapshot:",
        *lines,
    ]
    if today_bookings is not None:
        context.append(f"Bookings today: {today_bookings}")
    if people_today is not None:
        context.append(f"Total guests today: {people_today}")
    return "\n".join(context)


def answer(db, query: str) -> Optional[str]:
    """Agentic-style answer. Uses Ollama if enabled, with a planning-style system prompt.
    Optionally integrates with CrewAI or LangChain if installed, but degrades gracefully.
    """
    # Prepare world state
    world = _build_world_state(db)

    # If user asked for recommendations (date/romantic), give a stronger steer
    steer = ""
    ql = (query or "").lower()
    if any(key in ql for key in ["romantic", "date", "candlelight", "propose"]):
        steer = (
            "When the user asks for romantic/date ideas, recommend Lake view around sunset; "
            "for privacy recommend Private area; Window as cozy alternative."
        )

    system = (
        "You are an agentic restaurant assistant for Lake Serinity. Use the provided FACTS "
        "and reason step-by-step to answer succinctly (1-3 sentences), and include a suggestion "
        "or next action when useful. If the question asks about availability, suggest asking for "
        "date/time and party size to be precise. " + steer
    )

    prompt = (
        f"FACTS (fresh snapshot):\n{world}\n\n"
        f"QUESTION: {query}\n\n"
        "Answer:"
    )

    # CrewAI path if requested and available
    if settings.agent_type.lower() == "crewai":
        try:
            # Lazy import; do not require crewai at install time
            from crewai import Agent as CrewAgent, Task as CrewTask, Crew

            agent = CrewAgent(
                role="Restaurant Assistant",
                goal="Assist users with table bookings, availability, and general queries for Lake Serinity.",
                backstory="You are knowledgeable about the restaurant's operations, address, hours, and table layout.",
                allow_delegation=False,
                verbose=False,
            )
            task = CrewTask(
                description=f"Use the FACTS to answer.\n\n{prompt}",
                expected_output="A concise, accurate answer (1-3 sentences).",
                agent=agent,
            )
            crew = Crew(agents=[agent], tasks=[task])
            out = crew.kickoff()
            if out:
                return str(out).strip()
        except Exception:
            # Fall back to Ollama below
            pass

    # Prefer Ollama-based reasoning (works with or without LangChain installed)
    reply = ask_ollama(prompt=prompt, system=system, max_tokens=256)
    if reply:
        return reply.strip()

    # Fallback: return None to let the caller decide the next step
    return None
