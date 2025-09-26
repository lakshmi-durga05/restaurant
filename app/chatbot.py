from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional, Any
from uuid import uuid4
from datetime import datetime

from . import schemas, reservation_service
from .config import settings
from . import rag
from . import agents
from .llm import ask_ollama
from . import notify

# In-memory session store (for demo)
_sessions: Dict[str, "ChatSession"] = {}


@dataclass
class ChatSession:
    id: str
    state: str = "start"
    data: Dict[str, Any] = field(default_factory=dict)

    def next_prompt(self) -> str:
        prompts = {
            "start": "Hey there! Welcome to Lake Serinity. I can book a table, suggest options, and even take a pre-order. May I have your full name?",
            "ask_email": "Lovely! What email should we use for your confirmation?",
            "ask_phone": "Thanks. Could you share your phone number (e.g., +14155552671)?",
            "ask_party": "Great—how many people are joining?",
            "ask_date": "Noted. Which date would you like? (YYYY-MM-DD)",
            "ask_time": "And what time? (HH:MM, 24-hour format)",
            "ask_view": "Do you prefer a view? You can say window, garden, private, lake, rooftop, patio—or 'no'.",
            "confirm": "All set! Shall I check availability and place the booking now? (yes/no)",
            "offer_order": "Would you like to pre-order a few specials so they're ready when you arrive? (yes/no)",
            "ordering": "Sure! Use: add <item_id|name> [qty], remove <item_id|name>, list, help, or done to finish ordering.",
        }
        return prompts.get(self.state, "How can I help you next?")


def get_or_create_session(session_id: Optional[str]) -> ChatSession:
    if session_id and session_id in _sessions:
        return _sessions[session_id]
    sid = session_id or str(uuid4())
    sess = ChatSession(id=sid)
    _sessions[sid] = sess
    return sess


def _normalize_view(text: str) -> Optional[str]:
    t = text.lower().strip()
    # Strip common suffix words without losing the core token
    for suffix in (" view", " section", " area"):
        if t.endswith(suffix):
            t = t[: -len(suffix)]
            t = t.strip()
    # Direct matches
    if t in ("window", "garden", "private", "lake"):
        return t
    # If the phrase contains one of the known view words, pick it
    for v in ("window", "garden", "private", "lake"):
        if v in t.split() or v in t:
            return v
    # Explicit no-preference
    if t in ("no", "none", "any", "no preference"):
        return None
    return None


def _format_menu_items(items) -> str:
    parts = []
    for m in items:
        flag = " (special)" if getattr(m, 'is_special', False) else ""
        parts.append(f"{m.id}. {m.name} - ${m.price:.2f}{flag}")
    return "\n".join(parts) if parts else "Menu is currently unavailable."


def _parse_booking_info(sess: ChatSession, text: str):
    """Extract booking details from free-form customer text and store into sess.data.
    Does not overwrite existing fields unless the new text clearly provides them.
    """
    import re
    t = text.strip()
    lower = t.lower()
    # If the message is quoted and/or prefixed with 'book', normalize it
    # Examples: book 'Priya Shah, 2025-09-30 19:30, party 4, window, priyanka@example.com, +14155552671'
    t_norm = t
    if lower.startswith("book ") and not lower.startswith("book table"):
        t_norm = t[5:].strip()  # drop 'book '
    # remove surrounding quotes if present
    if (t_norm.startswith("'") and t_norm.endswith("'")) or (t_norm.startswith('"') and t_norm.endswith('"')):
        t_norm = t_norm[1:-1].strip()
    # CSV-style quick parse: Name, YYYY-MM-DD HH:MM, party N, view, email, phone
    try:
        parts_csv = [p.strip() for p in t_norm.split(',')]
        if len(parts_csv) >= 2 and "customer_name" not in sess.data:
            first = parts_csv[0]
            # Likely a full name if has at least one space and letters, and not an email or date/time
            import re as _re
            if ("@" not in first) and (_re.search(r"[A-Za-z]", first)) and ("-" not in first or not _re.search(r"\d{4}-\d{2}-\d{2}", first)):
                sess.data["customer_name"] = first.title()
        # If we have 2nd token like date/time, allow later regex to pick it up
    except Exception:
        pass

    # Email
    if "@" in t and "customer_email" not in sess.data:
        # naive pick first email-looking token
        m = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", t)
        if m:
            sess.data["customer_email"] = m.group(0)

    # Phone (10-15 digits)
    if "customer_phone" not in sess.data:
        m = re.search(r"\+?\d{8,15}", t.replace(" ", ""))
        if m:
            sess.data["customer_phone"] = m.group(0)

    # Date YYYY-MM-DD or relative words like today/tomorrow
    if "date" not in sess.data:
        m = re.search(r"\b\d{4}-\d{2}-\d{2}\b", t)
        if m:
            sess.data["date"] = m.group(0)
        else:
            # relative date
            if re.search(r"\btomorrow\b", lower):
                from datetime import datetime, timedelta
                d = datetime.utcnow().date() + timedelta(days=1)
                sess.data["date"] = d.strftime("%Y-%m-%d")
            elif re.search(r"\btoday\b", lower):
                from datetime import datetime
                d = datetime.utcnow().date()
                sess.data["date"] = d.strftime("%Y-%m-%d")

    # Time HH:MM or 9pm / 9 pm / 9:30pm
    if "time" not in sess.data:
        m = re.search(r"\b\d{1,2}:\d{2}\b", t)
        if m:
            sess.data["time"] = m.group(0)
        else:
            m2 = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", lower)
            if m2:
                hr = int(m2.group(1))
                minute = int(m2.group(2) or 0)
                ap = m2.group(3)
                if ap == 'pm' and hr != 12:
                    hr += 12
                if ap == 'am' and hr == 12:
                    hr = 0
                sess.data["time"] = f"{hr:02d}:{minute:02d}"

    # Party size (look for patterns: 'for 4', 'party 4', '4 people', '10 seats')
    if "party_size" not in sess.data:
        # Prioritize explicit people/seats keywords
        m = re.search(r"\b(\d{1,2})\s*(?:people|ppl|members|seats)\b", lower)
        if not m:
            m = re.search(r"\bparty\s*(\d{1,2})(?!\d)\b", lower)
        if not m:
            # Safe 'for <n>' that won't capture the year of a date like 'for 2025-09-26'
            m = re.search(r"\bfor\s*(\d{1,2})(?!\d)\b", lower)
        if m:
            try:
                sess.data["party_size"] = int(m.group(1))
            except Exception:
                pass
        else:
            # if message is just a number and we're early, accept it
            m2 = re.fullmatch(r"\d{1,2}", lower)
            if m2:
                sess.data["party_size"] = int(m2.group(0))

    # View preferences; support phrases like 'lake view', 'garden view section', etc.
    v = _normalize_view(lower)
    if v is not None:
        sess.data["preferred_view"] = v

    # Specific table request: only accept explicit forms to avoid 'table 4 members' ambiguity
    # Accepted: 'table id 4', 'table number 4', 'table no 4', 'table #4'
    if "table_id" not in sess.data:
        m_tid = re.search(r"\btable\s*(?:id|number|no|#)\s*(\d{1,3})\b", lower)
        if m_tid and "members" not in lower and "people" not in lower:
            try:
                sess.data["table_id"] = int(m_tid.group(1))
            except Exception:
                pass

    # Name helpers
    def _extract_name(raw: str) -> Optional[str]:
        import re as _re
        m = _re.search(r"(?:i am|i'm|name is|this is)\s+([A-Za-z][A-Za-z\.\-']*(?:\s+[A-Za-z][A-Za-z\.\-']*)*)", raw, flags=_re.IGNORECASE)
        if m:
            return m.group(1).strip().title()
        return None

    # Name: if the session has no name and the text looks like a name phrase
    if "customer_name" not in sess.data:
        # Guard: ignore obvious non-name queries so we don't mistake them for names
        non_name_keywords = [
            "available", "availability", "tables", "table", "menu", "special", "speciality",
            "specialty", "dish", "dishes", "view", "views", "price", "how much", "address",
            "hours", "time", "open", "close", "feature", "features", "help"
        ]
        if any(k in lower for k in non_name_keywords):
            pass
        else:
            name = _extract_name(text)
            if name:
                sess.data["customer_name"] = name
            else:
                # Fallback: if message is just two words letters-only, treat as name
                import re as _re
                if _re.fullmatch(r"[A-Za-z]{2,}(\s+[A-Za-z]{2,}){0,2}", text.strip()):
                    sess.data["customer_name"] = text.strip().title()
        if any(k in lower for k in ["i am ", "i'm ", "name is ", "this is "]):
            nm = _extract_name(text)
            if nm and len(nm) >= 2:
                sess.data["customer_name"] = nm
        else:
            # Only accept fallback as a likely full name: two words with letters (e.g., "Priya Shah")
            greetings = {"hi", "hello", "hey", "hola", "namaste", "thanks", "thank you"}
            if lower in greetings:
                pass
            else:
                # two or more alphabetic words
                parts = [p for p in re.split(r"\s+", t) if any(ch.isalpha() for ch in p)]
                if len(parts) >= 2 and "@" not in t and not re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}", t):
                    sess.data["customer_name"] = " ".join(parts).title()


def _missing_fields(sess: ChatSession) -> list:
    # Require: name, party_size, date, time, and both contacts (email and phone) to satisfy API schema
    missing = []
    for key in ["customer_name", "party_size", "date", "time"]:
        if key not in sess.data:
            missing.append(key)
    if "customer_email" not in sess.data:
        missing.append("customer_email")
    if "customer_phone" not in sess.data:
        missing.append("customer_phone")
    return missing


def handle_message(db, session_id: Optional[str], msg: str, locale: Optional[str] = None) -> dict:
    sess = get_or_create_session(session_id)
    msg = (msg or "").strip()

    def reply(text: str, done: bool = False, extra: Optional[Dict[str, Any]] = None):
        base = {"session_id": sess.id, "reply": text, "done": done}
        if extra:
            base.update(extra)
        return base

    # First, handle initial load (empty message): greet politely
    if not msg:
        return reply("Hello! How can I help you?")

    # Parse any booking info embedded in the message (customer-led)
    _parse_booking_info(sess, msg)

    # Global intents (can be asked at any time)
    lower = msg.lower().strip()

    # Save locale for session
    if locale:
        sess.data["_locale"] = locale

    # If message likely not English and Ollama is enabled, translate to English before parsing
    if sess.data.get("_locale") and str(sess.data["_locale"]).lower().startswith(("hi", "kn", "te", "ta", "ml", "mr", "bn")):
        tr = ask_ollama(
            prompt=f"Translate this to English. Return only the translation, no commentary.\n\n{msg}",
            system="You are a translator.",
            max_tokens=256,
        )
        if tr and isinstance(tr, str):
            msg = tr.strip()
            lower = msg.lower()

    # Friendly help at any time
    if lower in ("help", "menu help", "what can you do", "options"):
        examples = [
            "Start a booking: just tell me your name",
            "Availability: 'available tables', 'available tables now in garden'",
            "Counts: 'how many bookings happened today', 'how many people booked today'",
            "Who booked: 'who booked today', 'who booked table 3 today'",
            "Views: 'tables available in rooftop', 'tables booked in lake'",
            "Pre-order: 'add Serenity Butter Chicken 2', 'list', 'done'",
            "Tips: 'view garden' to switch your preferred view",
        ]
        return reply("Here’s what I can help with:\n- " + "\n- ".join(examples))

    # Cancellation intent (last confirmed booking)
    if any(k in lower for k in ["cancel reservation", "cancel my booking", "cancel booking"]):
        rid = sess.data.get("_last_reservation_id")
        if not rid:
            return reply("I couldn't find your last reservation in this session to cancel.")
        ok = reservation_service.cancel_reservation(db, int(rid))
        if ok:
            return reply("Your reservation has been cancelled.")
        return reply("I couldn't cancel it. It may already be cancelled or not found.")

    # Reschedule intent (use last booking and parse new datetime)
    if any(k in lower for k in ["reschedule", "change time", "change date", "postpone", "prepone"]):
        rid = sess.data.get("_last_reservation_id")
        if not rid:
            return reply("I couldn't find your last reservation in this session to reschedule.")
        # Try to parse date/time from the message
        backup = sess.data.copy()
        _parse_booking_info(sess, msg)
        if "date" not in sess.data and "time" not in sess.data:
            sess.data = backup
            return reply("Please include the new date and/or time in your message to reschedule.")
        try:
            new_dt = None
            if "date" in sess.data and "time" in sess.data:
                new_dt = datetime.fromisoformat(f"{sess.data['date']}T{sess.data['time']}:00")
            elif "date" in sess.data:
                new_dt = datetime.fromisoformat(f"{sess.data['date']}T00:00:00")
            elif "time" in sess.data and "date" not in sess.data and "_last_res_dt" in sess.data:
                old = datetime.fromisoformat(sess.data["_last_res_dt"]) 
                hh, mm = sess.data['time'].split(":")
                new_dt = old.replace(hour=int(hh), minute=int(mm))
        except Exception:
            new_dt = None
        sess.data = backup
        if not new_dt:
            return reply("I couldn't understand the new date/time. Please try again like 'reschedule to 2025-09-28 19:30'.")
        ok, message = reservation_service.reschedule_reservation(db, int(rid), new_dt)
        if ok:
            sess.data["_last_res_dt"] = new_dt.isoformat()
            return reply(f"Your reservation has been moved to {new_dt.strftime('%Y-%m-%d %H:%M')}.")
        return reply(message or "Sorry, I couldn't reschedule to that time.")

    # Greetings – greet and list available views
    if lower in ("hi", "hello", "hey", "hola", "namaste"):
        views = [v for v in reservation_service.get_all_views(db) if v not in ("rooftop", "patio", "palo")]
        views_text = ", ".join(views) if views else "window, garden, private, lake"
        return reply(f"Hello! How can I help you?\nAvailable views: {views_text}")
    # Lightweight pre-order commands (customer-led, available any time)
    def _find_menu_item(token: str):
        menu = reservation_service.get_menu(db)
        if token.isdigit():
            mid = int(token)
            for m in menu:
                if m.id == mid:
                    return m
        token_low = token.lower()
        for m in menu:
            if token_low in m.name.lower():
                return m
        return None

    parts = lower.split()
    if parts:
        if parts[0] == "add" and len(parts) >= 2:
            qty = 1
            # If last token is a digit, treat it as quantity
            if parts[-1].isdigit():
                qty = int(parts[-1])
                name_token = " ".join(parts[1:-1]) if len(parts) > 2 else parts[1]
            else:
                name_token = " ".join(parts[1:])
            m = _find_menu_item(name_token)
            if not m:
                return reply("I couldn't find that item. Try 'menu show' or 'help'.")
            # If we have a last confirmed reservation, append directly to DB
            last_res_id = sess.data.get("_last_reservation_id")
            if last_res_id:
                ok = reservation_service.add_items_to_reservation(db, int(last_res_id), [{"menu_item_id": int(m.id), "quantity": int(qty)}])
                if ok:
                    return reply(f"Added {m.name} x{qty} to your confirmed booking.")
                # fall back to cart if something went wrong
            cart = sess.data.get("items", [])
            cart.append({"menu_item_id": int(m.id), "quantity": int(qty)})
            sess.data["items"] = cart
            return reply(f"Added {m.name} x{qty}. When you share booking details, I will include these.")
        if parts[0] == "remove" and len(parts) >= 2:
            name_token = " ".join(parts[1:])
            m = _find_menu_item(name_token)
            if not m:
                return reply("I couldn't find that item to remove.")
            cart = [it for it in sess.data.get("items", []) if it.get("menu_item_id") != int(m.id)]
            sess.data["items"] = cart
            return reply(f"Removed {m.name}.")
        if parts[0] == "list" and len(parts) == 1:
            # If a reservation is already confirmed in this session, list its items from DB
            last_res_id = sess.data.get("_last_reservation_id")
            if last_res_id:
                pairs = reservation_service.get_reservation_items(db, int(last_res_id))
                if not pairs:
                    return reply("No items added to your confirmed booking yet.")
                out = ", ".join([f"{name} x{qty}" for name, qty in pairs])
                return reply(f"Your booking items: {out}")
            # otherwise, show the local cart
            cart = sess.data.get("items", [])
            if not cart:
                return reply("No items yet. Use 'add <name> [qty]'.")
            menu = reservation_service.get_menu(db)
            name_by_id = {m.id: m.name for m in menu}
            out = ", ".join([f"{name_by_id.get(it['menu_item_id'], it['menu_item_id'])} x{it['quantity']}" for it in cart])
            return reply(f"Current items: {out}")

    # List views or features on demand
    if any(k in lower for k in ["list views", "views available", "available views", "show views"]):
        views = [v for v in reservation_service.get_all_views(db) if v not in ("rooftop", "patio", "palo")]
        if not views:
            return reply("No views are configured yet.")
        return reply("Available views: " + ", ".join(views))
    if any(k in lower for k in ["list features", "show features", "features available", "available features"]):
        feats = reservation_service.list_features(db)
        if not feats:
            return reply("No features found.")
        return reply("Features: " + ", ".join(feats))

    if "booking" in lower and "today" in lower:
        count = reservation_service.count_bookings_today(db)
        return reply(f"We currently have {count} confirmed booking(s) today at Lake Serinity.")
    # Who booked (today default)
    if ("who" in lower and "book" in lower and "today" in lower) or ("who booked today" in lower):
        bookings = reservation_service.list_bookings_today(db)
        if not bookings:
            return reply("No confirmed bookings today yet.")
        lines = []
        for r in bookings[:20]:
            t = r.reservation_time.strftime("%H:%M") if r.reservation_time else "--:--"
            lines.append(f"- {r.customer_name} (party {r.party_size}) at {t}, table {r.table_id}")
        return reply("Today's bookings:\n" + "\n".join(lines))
    if ("who" in lower and "book" in lower and "table" in lower) and ("today" not in lower):
        # Default to today's list if timeframe is not specified
        bookings = reservation_service.list_bookings_today(db)
        if not bookings:
            return reply("No confirmed bookings today yet. You can also ask 'who booked this week'.")
        lines = []
        for r in bookings[:20]:
            t = r.reservation_time.strftime("%H:%M") if r.reservation_time else "--:--"
            lines.append(f"- {r.customer_name} (party {r.party_size}) at {t}, table {r.table_id}")
        return reply("Today's bookings:\n" + "\n".join(lines))

    # Who booked table <id> today
    if ("who" in lower and "book" in lower and "table" in lower and "today" in lower):
        # try to extract table id
        import re
        m = re.search(r"table\s*(\d+)", lower)
        if m:
            tid = int(m.group(1))
            rows = reservation_service.list_bookings_today_by_table(db, tid)
            if not rows:
                return reply(f"No confirmed bookings today for table {tid}.")
            lines = []
            for r in rows[:20]:
                t = r.reservation_time.strftime("%H:%M") if r.reservation_time else "--:--"
                lines.append(f"- {r.customer_name} (party {r.party_size}) at {t}")
            return reply(f"Today's bookings for table {tid}:\n" + "\n".join(lines))

    # Who booked <view> today / this week
    for view_name in ["garden", "window", "private", "lake", "rooftop", "patio"]:
        if ("who" in lower and "book" in lower and view_name in lower and "today" in lower):
            rows = reservation_service.list_bookings_today_by_view(db, view_name)
            if not rows:
                return reply(f"No confirmed bookings today for {view_name} view.")
            lines = []
            for r in rows[:25]:
                t = r.reservation_time.strftime("%H:%M") if r.reservation_time else "--:--"
                lines.append(f"- {r.customer_name} (party {r.party_size}) at {t}, table {r.table_id}")
            return reply(f"Today's bookings for {view_name} view:\n" + "\n".join(lines))
    if "people" in lower and "book" in lower and "today" in lower:
        total_people = reservation_service.count_people_booked_today(db)
        return reply(f"Total guests booked today: {total_people}")
    if ("who" in lower and "book" in lower and "week" in lower):
        week = reservation_service.list_bookings_week(db)
        if not week:
            return reply("No confirmed bookings this week yet.")
        lines = []
        for r in week[:25]:
            t = r.reservation_time.strftime("%Y-%m-%d %H:%M") if r.reservation_time else "--"
            lines.append(f"- {r.customer_name} (party {r.party_size}) at {t}, table {r.table_id}")
        return reply("This week’s bookings (latest):\n" + "\n".join(lines))

    # Main dishes intent
    if any(k in lower for k in ["speciality", "specialty", "special dish", "special dishes", "specials", "signature dishes", "chef special", "speciality of hotel", "specialty of hotel"]):
        menu = reservation_service.get_menu(db)
        specials = [m for m in menu if getattr(m, 'is_special', False)]
        if specials:
            lines = [f"- **{m.name}** – ${getattr(m,'price',0):.2f}" for m in specials[:10]]
            text = "\n".join(lines)
        else:
            text = "No special dishes today."
        hotel_features = [
            "Lakeside candlelight dinners",
            "Private gazebo seating",
            "Chef's table experience",
            "Sunset deck with live instrumental music (Fri–Sun)",
            "Kids' corner with activity kits",
            "Sommelier wine pairing recommendations",
            "Seasonal tasting menus crafted monthly",
            "Weekend lakeside brunch (Sat–Sun) with live griddle",
        ]
        features_text = "\n".join([f"- {f}" for f in hotel_features])
        sess.data["_awaiting_order_choice"] = True
        return reply(
            f"Special dishes (pre-order available):\n{text}\n\nHotel specialties:\n{features_text}\n\nWould you like to order now? (yes/no)"
        )
    if "menu" in lower and any(k in lower for k in ["show", "see", "list"]):
        menu = reservation_service.get_menu(db)
        text = _format_menu_items(menu[:10])
        sess.data["_awaiting_order_choice"] = True
        return reply(f"Here’s a peek at our menu (top items):\n{text}\nWould you like to order now? (yes/no)")

    # View stats: include booked details. If user has provided a target date/time (or just booked),
    # compute counts around that time (±2h). Otherwise, show next-24h summary.
    VIEWS = ["garden", "window", "private", "lake"]
    if (("available" in lower) or ("booked" in lower)) and any(v in lower for v in VIEWS):
        for v in VIEWS:
            if v in lower:
                target_dt = None
                # Try parsing date/time directly from this message without mutating the session
                try:
                    from copy import deepcopy as _dc
                    _tmp = ChatSession(id="tmp")
                    _parse_booking_info(_tmp, msg)
                    if all(k in _tmp.data for k in ["date", "time"]):
                        target_dt = datetime.fromisoformat(f"{_tmp.data['date']}T{_tmp.data['time']}:00")
                    elif "date" in _tmp.data and "time" not in _tmp.data:
                        target_dt = datetime.fromisoformat(f"{_tmp.data['date']}T00:00:00")
                except Exception:
                    pass
                try:
                    if not target_dt:
                        if all(k in sess.data for k in ["date", "time"]):
                            target_dt = datetime.fromisoformat(f"{sess.data['date']}T{sess.data['time']}:00")
                        elif "_last_res_dt" in sess.data:
                            target_dt = datetime.fromisoformat(sess.data["_last_res_dt"])  # stored ISO
                except Exception:
                    target_dt = None

                if target_dt:
                    stats = reservation_service.view_stats(db, v, when=target_dt)
                    bookings = reservation_service.list_bookings_around_view(db, v, target_dt)
                    if bookings:
                        lines = []
                        for r in bookings[:25]:
                            t = r.reservation_time.strftime("%Y-%m-%d %H:%M") if r.reservation_time else "--"
                            lines.append(f"- {r.customer_name} (party {r.party_size}) at {t}, table {r.table_id}")
                        booked_block = "\n".join(lines)
                        img_url = f"/api/availability/image?view={v}&at={target_dt.isoformat()}"
                        return reply(
                            f"View: {v}\nTotal: {stats['total']}\nBooked: {stats['booked']}\nAvailable: {stats['available']}\nBooked details (±2h around {target_dt.strftime('%Y-%m-%d %H:%M')}):\n{booked_block}",
                            extra={"image_url": img_url}
                        )
                    img_url = f"/api/availability/image?view={v}&at={target_dt.isoformat()}"
                    return reply(
                        f"View: {v}\nTotal: {stats['total']}\nBooked: {stats['booked']}\nAvailable: {stats['available']}\nNo confirmed bookings in this ±2h window.",
                        extra={"image_url": img_url}
                    )
                else:
                    # If a date is known but no time, show stats for that date (00:00–24:00 UTC)
                    if "date" in sess.data and "time" not in sess.data:
                        try:
                            day = datetime.fromisoformat(f"{sess.data['date']}T00:00:00")
                            stats = reservation_service.view_stats_on_date(db, v, day)
                            bookings = reservation_service.list_bookings_on_date(db, v, day)
                        except Exception:
                            stats = reservation_service.view_stats_next24(db, v)
                            bookings = reservation_service.list_bookings_next24_by_view(db, v)
                    else:
                        stats = reservation_service.view_stats_next24(db, v)
                        bookings = reservation_service.list_bookings_next24_by_view(db, v)
                    if bookings:
                        lines = []
                        for r in bookings[:25]:
                            t = r.reservation_time.strftime("%Y-%m-%d %H:%M") if r.reservation_time else "--"
                            lines.append(f"- {r.customer_name} (party {r.party_size}) at {t}, table {r.table_id}")
                        booked_block = "\n".join(lines)
                        # Use date-only if time not specified in session
                        try:
                            at_iso = day.isoformat()
                        except Exception:
                            from datetime import datetime as _dt
                            at_iso = _dt.utcnow().isoformat()
                        img_url = f"/api/availability/image?view={v}&at={at_iso}"
                        return reply(
                            f"View: {v}\nTotal: {stats['total']}\nBooked: {stats['booked']}\nAvailable: {stats['available']}\nBooked details:\n{booked_block}",
                            extra={"image_url": img_url}
                        )
                    try:
                        at_iso = day.isoformat()
                    except Exception:
                        from datetime import datetime as _dt
                        at_iso = _dt.utcnow().isoformat()
                    img_url = f"/api/availability/image?view={v}&at={at_iso}"
                    return reply(
                        f"View: {v}\nTotal: {stats['total']}\nBooked: {stats['booked']}\nAvailable: {stats['available']}\nNo confirmed bookings for that period.",
                        extra={"image_url": img_url}
                    )

    # Summary across all views (no view specified)
    if ("available" in lower and ("tables" in lower or "table" in lower)) and not any(v in lower for v in VIEWS):
        # If user asked "available tables now" show specific table IDs
        if "now" in lower:
            tables = reservation_service.available_tables_now(db)
            if not tables:
                return reply("No tables are currently free in the next ±2 hours.")
            by_view: dict[str, list[str]] = {}
            for t in tables:
                by_view.setdefault(t.view, []).append(f"{t.id} (cap {t.capacity})")
            lines = [f"- {v}: " + ", ".join(ids) for v, ids in by_view.items()]
            return reply("Available tables now (IDs):\n" + "\n".join(lines) + "\nYou can book with 'book <table_id>'.")
        else:
            views = reservation_service.get_all_views(db)
            if not views:
                return reply("No tables configured yet.")
            lines = []
            for v in views:
                s = reservation_service.view_stats(db, v)
                lines.append(f"- {v}: total {s['total']}, booked {s['booked']}, available {s['available']}")
            return reply("Availability by view:\n" + "\n".join(lines), extra={"image_url": "/assets/hotel.jpg"})

    # If user just saw the menu/specialties and replies yes/no
    if sess.data.get("_awaiting_order_choice"):
        if lower in ("yes", "y"):
            sess.state = "ordering"
            sess.data.pop("_awaiting_order_choice", None)
            return reply(sess.next_prompt())
        if lower in ("no", "n"):
            sess.data.pop("_awaiting_order_choice", None)
            return reply("No problem. How else can I help you?")

    # Number of unique tables booked today
    if ("tables" in lower and "booked" in lower and "today" in lower) or ("how many booked" in lower and "today" in lower):
        cnt = reservation_service.tables_booked_today_count(db)
        return reply(f"Unique tables booked today: {cnt}")

    # Available tables now in a specific view
    if ("available tables now" in lower) and any(v in lower for v in VIEWS):
        for v in VIEWS:
            if v in lower:
                tables = reservation_service.available_tables_now(db, v)
                if not tables:
                    return reply(f"No {v} tables are currently free in the next ±2 hours.")
                ids = ", ".join([f"{t.id} (cap {t.capacity})" for t in tables])
                return reply(f"Available {v} tables now: {ids}\nBook with 'book <table_id>'.")

    # Total tables in hotel and per-view breakdown
    if any(k in lower for k in ["total number of tables", "total tables", "tables in hotel", "how many tables", "number of tables", "no of tables", "no. of tables", "total no of tables"]):
        total = reservation_service.total_tables_count(db)
        per_view = reservation_service.per_view_table_counts(db)
        view_lines = ", ".join([f"{v}: {c}" for v, c in per_view]) if per_view else ""
        msg_total = f"Total tables: {total}"
        if view_lines:
            msg_total += f" (by view: {view_lines})"
        return reply(msg_total)

    # Working hours / timings
    if any(k in lower for k in ["working hours", "timings", "opening hours", "open hours", "when do you open", "when do you close", "closing time", "opening time", "hours of operation", "hours", "timing"]):
        return reply("Lake Serinity is open daily from 11:00 AM to 11:00 PM. Last seating at 10:00 PM.\nLunch: 12:00 PM – 3:30 PM\nDinner: 6:30 PM – 11:00 PM")

    # Hotel address / location
    if any(k in lower for k in ["address", "location", "where are you", "where is the hotel", "where is lake serinity", "directions", "how to reach"]):
        return reply("Lake Serinity is located at:\n123 Serene Lake Drive, Lakeside District, Bangalore, Karnataka 560001, India\n\nFor directions, you can search 'Lake Serinity Restaurant' on Google Maps.")

    # Hotel contact details
    if any(k in lower for k in ["contact details", "phone number", "contact", "email id", "email address", "how to contact", "call you"]):
        return reply(
            "Contact details:\nPhone: +91 98765 43210\nEmail: reservations@lake-serinity.example\nAddress: 123 Serene Lake Drive, Lakeside District, Bangalore 560001\nHours: 12:00–23:00"
        )

    # Date/romantic suggestions (concise; include dish pairing)
    if any(k in lower for k in ["romantic", "date", "take someone on date", "propose", "candlelight"]):
        # Fetch a couple of house specials for a short pairing suggestion
        try:
            menu = reservation_service.get_menu(db)
            specials = [m for m in menu if getattr(m, 'is_special', False)]
            top = [m.name for m in specials[:2]] if specials else []
        except Exception:
            top = []
        dish_line = f" Try: {top[0]} with a light wine." if top else ""
        return reply(
            "For a romantic date, choose Lake view near sunset for a beautiful ambiance; Private area if you prefer privacy; Window as a cozy alternative." + dish_line
        )

    # If user asks for a 'special dish' explicitly, give 1-2 tailored items rather than full list
    if any(k in lower for k in ["special dish", "recommend a dish", "what to order", "signature dish"]):
        try:
            menu = reservation_service.get_menu(db)
            specials = [m for m in menu if getattr(m, 'is_special', False)]
            names = [m.name for m in specials[:2]] if specials else []
        except Exception:
            names = []
        if names:
            return reply(f"I'd suggest {names[0]}{(' and ' + names[1]) if len(names) > 1 else ''} — perfect for a date. Would you like to pre-order?")
        return reply("Our chef specials change often; I'd suggest the catch of the day. Would you like to see the menu?")

    # Allow quick view change: "view garden" or "garden view"
    if lower.startswith("view "):
        new_view = _normalize_view(lower.replace("view ", ""))
        if new_view is not None or lower.endswith("no"):
            sess.data["preferred_view"] = new_view
            return reply("Updated your preferred view. " + sess.next_prompt())

    # Customer-led booking: if enough info is present, auto-save immediately
    if not _missing_fields(sess) and sess.state != "ordering":
        try:
            dt = datetime.fromisoformat(f"{sess.data['date']}T{sess.data['time']}:00")
            reservation = schemas.ReservationCreate(
                customer_name=sess.data["customer_name"],
                customer_email=sess.data.get("customer_email") or "N/A",
                customer_phone=sess.data.get("customer_phone") or "N/A",
                reservation_time=dt,
                party_size=sess.data["party_size"],
                preferred_view=sess.data.get("preferred_view"),
                items=sess.data.get("items", []),
                table_id=sess.data.get("table_id"),
            )
        except Exception as e:
            return reply(f"I have most details, but something looks off: {e}")

        response = reservation_service.create_reservation(db, reservation)
        if response.success and response.reservation:
            sid = sess.id
            # Remember last reservation id so user can add dishes after confirmation
            last_id = getattr(response.reservation, "id", None) if response.reservation else None
            last_dt = None
            try:
                last_dt = response.reservation.reservation_time.isoformat() if response.reservation and response.reservation.reservation_time else None
            except Exception:
                last_dt = None
            sess.state = "start"
            sess.data.clear()
            if last_id:
                sess.data["_last_reservation_id"] = last_id
            if last_dt:
                sess.data["_last_res_dt"] = last_dt
            # Build WhatsApp reminder deeplink (no external providers)
            try:
                wa_text = (
                    f"Lake Serinity booking confirmed! %0A"
                    f"Time: {response.reservation.reservation_time} %0A"
                    f"Party: {response.reservation.party_size} %0A"
                    f"Table: {response.reservation.table_id}"
                )
                wa_link = notify.whatsapp_deeplink(
                    getattr(response.reservation, "customer_phone", ""),
                    f"Lake Serinity booking confirmed!\nTime: {response.reservation.reservation_time}\nParty: {response.reservation.party_size}\nTable: {response.reservation.table_id}"
                )
            except Exception:
                wa_link = None
            # Try to send a confirmation email if SMTP configured
            try:
                notify.send_confirmation_email(response.reservation)
            except Exception:
                pass
            msg_txt = "Done! Your table at Lake Serinity is confirmed."
            if wa_link:
                msg_txt += f"\nSet a WhatsApp reminder: {wa_link}"
            return reply(
                msg_txt,
                done=True,
                extra={"session_id": sid, "reservation": response.reservation.model_dump(mode="json")},
            )
        # Provide suggestions if not available
        suggestion = response.suggestions
        if suggestion and (suggestion.tables or suggestion.other_view_suggestions):
            # Persist suggested tables for quick 'book combo'
            if suggestion.tables:
                sess.data["_suggested_table_ids"] = [int(t.id) for t in suggestion.tables]
                try:
                    sess.data["_suggested_dt"] = dt.isoformat()
                except Exception:
                    pass
            elif suggestion.other_view_suggestions:
                sess.data["_suggested_table_ids"] = [int(t.id) for t in suggestion.other_view_suggestions]
            tables_text = ", ".join([f"Table {t.id} for {t.capacity} ({t.view})" for t in (suggestion.tables or [])])
            other_text = ", ".join([f"Table {t.id} for {t.capacity} ({t.view})" for t in (suggestion.other_view_suggestions or [])])
            msg_lines = [response.message]
            if tables_text:
                msg_lines.append(f"Suggested in preferred view: {tables_text}")
            if other_text:
                msg_lines.append(f"Other views: {other_text}")
            extra_hint = "You can book a specific one with 'book <table_id>'."
            if suggestion.tables and not suggestion.is_exact_match and len(suggestion.tables) >= 2:
                extra_hint += " Reply with 'book combo' to reserve the suggested tables together for your party."
            msg_lines.append(extra_hint)
            return reply("\n".join(msg_lines))
        return reply("Sorry, nothing is available for those exact details. Try a different time or say 'available tables now'.")

    # If information is incomplete, respond gently
    missing = _missing_fields(sess)
    if missing and sess.state != "ordering":
        # If the user just shared their name (and no other booking keywords), greet and offer help
        if (
            "customer_name" in sess.data
            and all(k not in sess.data for k in ["customer_email", "customer_phone", "party_size", "date", "time"])  
            and not any(w in lower for w in ["book", "reserve", "table", "party", "date", "time", "window", "garden", "private", "lake", "rooftop", "patio"])
        ):
            views = reservation_service.get_all_views(db)
            views_text = ", ".join(views) if views else "window, garden, private, lake, rooftop, patio"
            return reply(f"Nice to meet you, {sess.data['customer_name']}. How can I help you?\nAvailable views: {views_text}")
        pretty = {
            "customer_name": "your full name",
            "party_size": "party size",
            "date": "date (YYYY-MM-DD)",
            "time": "time (HH:MM)",
            "customer_email": "email",
            "customer_phone": "phone",
        }
        need = ", ".join([pretty[m] for m in missing])
        return reply(f"Please provide: {need}. Example: 'Priya Shah, 2025-09-30 19:30, party 4, window, priyanka@example.com, +14155552671'.")

    if sess.state == "ask_email" and sess.state != "ordering":
        # Defer to customer-led guidance
        return reply("Please provide details in one message (include both email and phone). Example: 'Priya Shah, 2025-09-30 19:30, party 4, window, priyanka@example.com, +14155552671'.")

    if sess.state == "ask_phone" and sess.state != "ordering":
        return reply("Share remaining details in one go (include both email and phone): 'Name, YYYY-MM-DD HH:MM, party N, view, email, phone'.")

    if sess.state == "ask_party" and sess.state != "ordering":
        return reply("Share remaining details in one go: 'Name, YYYY-MM-DD HH:MM, party N, view, email, phone'.")

    if sess.state == "ask_date" and sess.state != "ordering":
        return reply("Please send: 'Name, YYYY-MM-DD HH:MM, party N, view, email, phone'.")

    if sess.state == "ask_time" and sess.state != "ordering":
        return reply("Please send: 'Name, YYYY-MM-DD HH:MM, party N, view, email, phone'.")

    if sess.state == "ask_view" and sess.state != "ordering":
        return reply("Add your preferred view in your message if you have one (window/garden/private/lake/rooftop/patio).")

    if sess.state == "confirm" and sess.state != "ordering":
        return reply("Once you provide all details in one message, I’ll confirm your table right away.")

    # Fallback: RAG/LLM answers for general questions (does not affect booking flow)
    if settings.use_rag:
        ans = rag.answer(db, msg)
        if ans:
            return reply(ans)
    # Agentic AI fallback (optional)
    if settings.use_agents:
        a = agents.answer(db, msg)
        if a:
            return reply(a)

    # Default friendly response
    return reply("I can help with bookings, availability, menu, and more. Try 'help' to see examples.")

    if sess.state == "offer_order":
        if msg.lower() in ("yes", "y"):
            sess.state = "ordering"
            return reply(sess.next_prompt())
        if msg.lower() in ("no", "n"):
            # Create reservation without items
            reservation = sess.data.get("_pending_reservation")
            response = reservation_service.create_reservation(db, reservation)
            if response.success and response.reservation:
                sess.state = "start"
                sess.data.clear()
                return reply("Your reservation at Lake Serinity is confirmed!", done=True, extra={"reservation": response.reservation.model_dump(mode="json")})
            # Provide alternative suggestions
            suggestion = response.suggestions
            if suggestion and (suggestion.tables or suggestion.other_view_suggestions):
                tables_text = ", ".join([f"Table {t.id} for {t.capacity} ({t.view})" for t in (suggestion.tables or [])])
                other_text = ", ".join([f"Table {t.id} for {t.capacity} ({t.view})" for t in (suggestion.other_view_suggestions or [])])
                msg_text = response.message
                if other_text:
                    msg_text += f"\nOther views: {other_text}"
                # Persist for combo booking
                if suggestion.tables:
                    sess.data["_suggested_table_ids"] = [int(t.id) for t in suggestion.tables]
                return reply(f"{msg_text}\nReply with 'book <table_id>' to confirm a specific table or 'book combo' to reserve multiple tables, or 'view <name>' to change view.")
            sess.state = "start"
            sess.data.clear()
            return reply("Sorry, nothing is available. Try a different time or party size.")
        return reply("Please answer 'yes' or 'no'.")

    if sess.state == "ordering":
        text = msg.strip()
        parts = text.split()
        items: list[dict] = sess.data.get("items", [])

        def find_menu_item(token: str):
            menu = reservation_service.get_menu(db)
            if token.isdigit():
                mid = int(token)
                for m in menu:
                    if m.id == mid:
                        return m
            # match by name (case-insensitive, partial)
            token_low = token.lower()
            # reconstruct full name from everything after the command
            for m in menu:
                if token_low in m.name.lower():
                    return m
            return None

        if parts and parts[0].lower() == "help":
            menu = reservation_service.get_menu(db)
            example = _format_menu_items(menu[:5])
            return reply("Examples:\n- add 4 2\n- add Woodfired Paneer Tikka 1\n- remove Paneer\n- list\n- done\n\nTop items:\n" + example)

        if parts and parts[0].lower() == "add" and len(parts) >= 2:
            # quantity optional (default 1). If last token is digit treat as qty.
            qty = 1
            if parts[-1].isdigit():
                qty = int(parts[-1])
                name_token = " ".join(parts[1:-1]) if len(parts) > 2 else parts[1]
            else:
                name_token = " ".join(parts[1:])
            m = find_menu_item(name_token)
            if not m:
                return reply("I couldn't find that item. Type 'help' to see examples or 'menu show' to list items.")
            items.append({"menu_item_id": int(m.id), "quantity": int(qty)})
            sess.data["items"] = items
            return reply(f"Added {m.name} x{qty}. Type 'done' when finished or 'list' to review.")

        if parts and parts[0].lower() == "remove" and len(parts) >= 2:
            name_token = " ".join(parts[1:])
            m = find_menu_item(name_token)
            if not m:
                return reply("I couldn't find that item to remove.")
            items = [it for it in items if it.get("menu_item_id") != int(m.id)]
            sess.data["items"] = items
            return reply(f"Removed {m.name}.")

        if parts and parts[0].lower() == "list":
            if not items:
                return reply("No items yet. Use 'add <item_id|name> [qty]'.")
            # show item names
            menu = reservation_service.get_menu(db)
            name_by_id = {m.id: m.name for m in menu}
            out = ", ".join([f"{name_by_id.get(it['menu_item_id'], it['menu_item_id'])} x{it['quantity']}" for it in items])
            return reply(f"Current items: {out}")

        if parts and parts[0].lower() == "done":
            # Create reservation with items
            reservation: schemas.ReservationCreate = sess.data.get("_pending_reservation")
            reservation.items = sess.data.get("items", [])
            response = reservation_service.create_reservation(db, reservation)
            if response.success and response.reservation:
                sess.state = "start"
                sess.data.clear()
                return reply("Your reservation at Lake Serinity is confirmed with pre-order!", done=True, extra={"reservation": response.reservation.model_dump(mode="json")})
            suggestion = response.suggestions
            if suggestion and (suggestion.tables or suggestion.other_view_suggestions):
                tables_text = ", ".join([f"Table {t.id} for {t.capacity} ({t.view})" for t in (suggestion.tables or [])])
                other_text = ", ".join([f"Table {t.id} for {t.capacity} ({t.view})" for t in (suggestion.other_view_suggestions or [])])
                msg_text = response.message
                if other_text:
                    msg_text += f"\nOther views: {other_text}"
                return reply(f"{msg_text}\nReply with 'book <table_id>' to confirm a specific table or 'view <name>' to change view.")
            sess.state = "start"
            sess.data.clear()
            return reply("Sorry, nothing is available. Try a different time or party size.")
        return reply(sess.next_prompt())

        # Provide suggestions text
        suggestion = response.suggestions
        if suggestion and suggestion.tables:
            tables_text = ", ".join([f"Table {t.id} for {t.capacity} ({t.view})" for t in suggestion.tables])
            # Store for combo flow
            sess.data["_suggested_table_ids"] = [int(t.id) for t in suggestion.tables]
            return reply(
                f"{response.message}\nSuggested: {tables_text}.\nReply with 'book <table_id>' or 'book combo' to reserve suggested tables.",
                extra={"suggestions": [t.id for t in suggestion.tables]},
            )
        else:
            sess.state = "start"
            sess.data.clear()
            return reply("Sorry, nothing is available. Try a different time or party size.", done=True)

    # Quick command: book <table_id>
    if msg.lower().startswith("book "):
        parts = msg.split()
        # 'book combo' -> reserve suggested split tables
        if len(parts) == 2 and parts[1].lower() == "combo":
            ids = sess.data.get("_suggested_table_ids") or []
            if not ids:
                return reply("I don't have a suggested combination yet. Ask for availability first.")
            required = ["customer_name", "party_size", "date", "time"]
            has_both_contacts = ("customer_email" in sess.data) and ("customer_phone" in sess.data)
            if (not all(k in sess.data for k in required)) or (not has_both_contacts):
                return reply("Please complete details first (name, party, date, time, email and phone). Then say 'book combo'.")
            dt = datetime.fromisoformat(f"{sess.data['date']}T{sess.data['time']}:00")
            payload = {
                "customer_name": sess.data["customer_name"],
                "customer_email": sess.data["customer_email"],
                "customer_phone": sess.data["customer_phone"],
                "reservation_time": dt.isoformat(),
                "party_size": int(sess.data["party_size"]),
                "preferred_view": sess.data.get("preferred_view"),
                "table_ids": list(ids),
            }
            try:
                out = reservation_service.create_combo_reservations(db, payload)
                if out and out.get("success"):
                    sess.state = "start"
                    sess.data.clear()
                    return reply(out.get("message") or "Reserved the suggested tables for your party.", done=True)
                return reply(out.get("message") if out else "Unable to create combo reservation.")
            except Exception as e:
                return reply(f"Couldn't create combo reservation: {e}")

        if len(parts) == 2 and parts[1].isdigit():
            table_id = int(parts[1])
            required = ["customer_name", "party_size", "date", "time"]
            has_both_contacts = ("customer_email" in sess.data) and ("customer_phone" in sess.data)
            if (not all(k in sess.data for k in required)) or (not has_both_contacts):
                return reply("Please complete the details first (name, party, date, time, email and phone).")
            dt = datetime.fromisoformat(f"{sess.data['date']}T{sess.data['time']}:00")
            reservation = schemas.ReservationCreate(
                customer_name=sess.data["customer_name"],
                customer_email=sess.data["customer_email"],
                customer_phone=sess.data["customer_phone"],
                reservation_time=dt,
                party_size=sess.data["party_size"],
                preferred_view=sess.data.get("preferred_view"),
                table_id=table_id,
                items=sess.data.get("items", []),
            )
            resp = reservation_service.create_reservation(db, reservation)
            if resp.success:
                sess.state = "start"
                sess.data.clear()
                return reply("Booked! Your reservation at Lake Serinity is confirmed.", done=True, extra={"reservation": resp.reservation.model_dump(mode="json")})
            return reply(resp.message or "Unable to book that table.")
        return reply("Usage: book <table_id>")

    return reply(sess.next_prompt())
