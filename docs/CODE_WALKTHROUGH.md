# Lake Serinity – Code Walkthrough (Detailed)

This document provides a deep dive into the project’s codebase, explaining the purpose of each module, important functions and classes, and how the booking + availability workflow is implemented end‑to‑end.

---

## Directory layout

```
restaurant_booking/
  app/
    chatbot.py
    reservation_service.py
    models.py
    database.py
    main.py
    config.py
    rag.py
    llm.py
    notify.py
  templates/
    chat.html
    customers.html
    book.html
    db.html
  docs/
    PROJECT_OVERVIEW.md
    CODE_WALKTHROUGH.md   (this file)
    API_REFERENCE.md
    DATABASE_SCHEMA.md
    RAG_LANGCHAIN_OLLAMA.md
```

---

## app/main.py
- Creates the FastAPI app, configures CORS, mounts routes.
- Ensures DB tables exist and calls `reservation_service.purge_views(..., ["rooftop","patio","palo"])` at startup (idempotent cleanup).
- Routes of interest (documented in `API_REFERENCE.md`):
  - `/chat` (template), `/api/chatbot/message` (chat API), admin pages `/admin/customers`, `/admin/db`, `/admin/db/view`.

---

## app/database.py
- `SessionLocal`, `engine`, and `Base` for SQLAlchemy.
- Dependency `get_db()` yields a SQLAlchemy session per request.

---

## app/models.py
- SQLAlchemy models and seed logic.
- Models:
  - `Table(id, capacity, view, is_available, features)`
  - `Feature(id, name)` with `table_features` association table
  - `Reservation(id, customer_name, customer_email, customer_phone, reservation_time, party_size, table_id, status, created_at, special_requests)`
  - `MenuItem(id, name, description, price, is_special)`
  - `ReservationItem(id, reservation_id, menu_item_id, quantity)`
- `init_db()` performs lightweight migrations and seeds sample data (including expanded mains/specials). Only `lake` is ensured; removed views are not recreated.

---

## app/reservation_service.py
- Core business logic for reservations and availability.
- Highlights:
  - `create_reservation(db, schemas.ReservationCreate)`
    - Validates that a table exists (by view / or selected `table_id`), capacity fits, and no conflicting bookings exist in the ±2h window.
    - Smart suggestions when the requested table/time is not available (split tables or other views).
  - Availability statistics and listings:
    - `view_stats(db, view, when)` → Total, Booked, Available, using case‑insensitive view match and ±2h around `when`.
    - `list_bookings_around_view(db, view, center_time)` → Confirmed bookings in ±2h window.
    - `view_stats_on_date(db, view, day)` and `list_bookings_on_date(...)` → whole day.
    - `view_stats_next24(db, view)` and `list_bookings_next24_by_view(...)` → next 24h.
  - Post‑booking items:
    - `add_items_to_reservation(...)`, `get_reservation_items(...)`.
  - Maintenance/admin:
    - `purge_views(...)`, `reschedule_reservation(...)`, and `cancel_reservation(...)`.

---

## app/chatbot.py
- Customer‑led conversation logic. Important components:
  - `ChatSession` – stores ephemeral state + data.
  - `_parse_booking_info(sess, text)` extracts:
    - `customer_name`, `party_size` (“party 4”, “4 members”), `date` (“2025‑09‑30”), `time` (“19:30” / “7:30pm”), `preferred_view` (window/garden/private/lake), optional `table_id` for explicit forms (“table number 4”), and `customer_email`/`customer_phone`.
  - `_missing_fields(sess)` – booking requires: name, party size, date, time, and at least one contact (email or phone).
  - `handle_message(db, session_id, msg, locale=None)`
    - Greets and lists available views (excluding removed ones).
    - Handles specials/menu/main‑dishes intents and returns friendly prompts to pre‑order.
    - Booking: when all fields are present → builds `schemas.ReservationCreate` and calls `reservation_service.create_reservation(...)`.
      - On success: stores `_last_reservation_id`, `_last_res_dt`, sends email (optional) and shows a WhatsApp reminder deeplink.
    - Availability (by view):
      - Parses date/time from the availability message itself first (without mutating the session).
      - If found → ±2h stats, else try session date/time, else next‑24h or day‑only as appropriate.
      - Always lists customer details under booked tables for the chosen period.
    - Post‑booking add/list items uses DB when `_last_reservation_id` is present, else a temporary cart.
    - Cancellation and reschedule are supported by natural phrases.
 
- Guard rails:
  - Speciality of hotel queries won’t be misinterpreted as a customer name.

---

## app/rag.py
- Builds a small TF‑IDF corpus combining:
  - Menu items (names, descriptions, prices)
  - Views and short operational info / FAQs
- Uses cosine similarity to select top‑K documents for a query and compose a short answer.
- Triggered only when the chatbot didn’t match any operational/booking intents.

---

## app/llm.py
- `ask_ollama(prompt, system=None, max_tokens=512)`
  - If `USE_OLLAMA=true`, tries LangChain’s `langchain_community.llms.Ollama` first.
  - If unavailable or fails, falls back to Ollama REST API at `http://localhost:11434/api/generate`.
  - This layer is optional; the bot works without it.

---

## app/notify.py
- `send_confirmation_email(reservation)` – SMTP email confirmation (best effort).
- `whatsapp_deeplink(phone, text)` – builds a `wa.me` uniform link that opens WhatsApp with pre‑filled message (no external provider).

---

## templates/chat.html
- Modern chat UI with:
  - Voice input (Web Speech API) and optional TTS for replies.
  - Buttons for “View Customers” and “View Database”.
  - Availability and booked details are presented as plain text blocks.

---

## End‑to‑end booking & availability flow
1. User sends natural text containing name, date, time, party size, and contact.
2. `chatbot._parse_booking_info()` extracts fields.
3. `chatbot.handle_message()` calls `reservation_service.create_reservation()`.
4. On success:
   - WhatsApp deeplink and (optional) email confirmation are sent.
   - `_last_reservation_id` and `_last_res_dt` are stored.
5. For “available tables in <view> [for <date> [<time>]]”:
   - The chatbot attempts to parse date/time from that message specifically.
   - Computes counts using `reservation_service.view_stats(...)` (±2h) or date/next‑24h.
   - Lists customers under booked tables.

---

## Troubleshooting tips
- If availability shows Booked=0 after booking, include the date/time in the availability query to pin the ±2h window, e.g. `available tables in garden view for 2025-09-30 19:30`.
- If LangChain/Ollama isn’t installed or running, booking still works; RAG answers non‑booking questions.
- To observe DB changes, open `/admin/db/view` or download `/admin/db`.

---

## Appendix – Important symbols to review
- `app/chatbot.py: handle_message(), _parse_booking_info(), _missing_fields()`
- `app/reservation_service.py: create_reservation(), view_stats(), list_bookings_around_view()`
- `app/llm.py: ask_ollama()`
- `app/rag.py: answer()`
- `app/notify.py: whatsapp_deeplink()`
