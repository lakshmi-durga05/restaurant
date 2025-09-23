# Lake Serinity Restaurant Chatbot – Technical Overview

This document explains the main code, architecture, data model, booking/availability logic, RAG/Ollama/LangChain integrations, and admin/UX features in this project. It also lists tested versions and how to run the app.

---

## 1) Architecture

- **FastAPI** (`app/main.py`)
  - Serves API endpoints for chatbot, admin pages, and static views.
- **Jinja2 templates** (`templates/*.html`)
  - `chat.html` – main chatbot UI with voice input and optional TTS.
  - `customers.html` – today’s bookings.
  - `db.html` – database viewer (tables, reservations, items).
- **SQLite + SQLAlchemy**
  - Models in `app/models.py` and session management in `app/database.py`.
- **Chatbot core** (`app/chatbot.py`)
  - Customer-led parser; confirms bookings once sufficient info is present.
  - Availability logic (±2h, date-only, or next 24h).
  - RAG/Ollama fallback for general questions.
  - Cancellation and reschedule intents.
  - WhatsApp deeplink + optional email confirmation.
- **Business logic** (`app/reservation_service.py`)
  - Reservation creation with race-safety window.
  - Availability & booked counts by view and time windows.
  - Post-booking items, weekly/today stats, and purge helpers.
- **RAG + LLM**
  - `app/rag.py` – TF‑IDF retrieval over menu/views/FAQs.
  - `app/llm.py` – Ollama ask function with LangChain adapter and REST fallback.
  - `app/config.py` – feature flags and settings.

---

## 2) Data model (SQLAlchemy)

- `Table`: id, capacity, view, is_available
- `Feature`: name; many-to-many with tables
- `Reservation`: customer details, reservation_time, party_size, status, table_id
- `MenuItem`: name, description, price, is_special
- `ReservationItem`: reservation_id, menu_item_id, quantity

Seed data is created if DB is empty (including expanded mains/specials). Views `rooftop/patio/palo` are removed at startup and not recreated.

---

## 3) Key flows and files

- `app/chatbot.py`
  - Parses name, date, time, party size, contact (email or phone). Only one contact is required.
  - Auto-confirms booking via `reservation_service.create_reservation()`.
  - Stores `_last_reservation_id` (for adding dishes) and `_last_res_dt` (for availability queries).
  - Availability answers for specific views:
    - If current message has date+time → ±2h around that time.
    - If only date → whole date (00:00–24:00 UTC).
    - Else → next 24 hours.
    - Always prints Booked details (name, party, time, table).
  - Intents: "speciality of hotel", "main dishes", "menu", "add <item> [qty]", "list", "cancel reservation", "reschedule to <dt>".
  - Speciality response includes pre-order note and hotel-exclusive experiences.

- `app/reservation_service.py`
  - `create_reservation(...)` – Validates capacity, view matching, overlap within ±2h.
  - `view_stats(...)`, `list_bookings_around_view(...)` – Case-insensitive view filters; accurate ±2h counts.
  - `view_stats_on_date(...)`, `list_bookings_on_date(...)` – Day window.
  - `view_stats_next24(...)`, `list_bookings_next24_by_view(...)` – Next 24 hours.
  - `add_items_to_reservation(...)`, `get_reservation_items(...)` – Post-booking dishes.
  - `reschedule_reservation(...)`, `cancel_reservation(...)` – Admin/user intents.
  - `purge_views(...)` – Permanently delete disallowed views and related data.

---

## 4) RAG and LLM integration

- **RAG** (`app/rag.py`)
  - TF‑IDF (`scikit-learn`) over menu, views, and FAQs.
  - Returns top‑K snippets used to answer general questions when booking logic doesn’t match.
- **Ollama** (`app/llm.py`)
  - `ask_ollama()` prefers LangChain’s community Ollama wrapper when available and falls back to the Ollama REST API.
  - Controlled by env flags in `app/config.py`.
- **LangChain**
  - Optional. If installed, `langchain_community.llms.Ollama` is used automatically.

---

## 5) Voice & notifications

- **Voice input**
  - `templates/chat.html` adds a mic button using the Web Speech API to transcribe speech and send as a message.
  - Optional TTS reads bot replies when enabled by the checkbox.
- **Notifications** (`app/notify.py`)
  - Email confirmation via SMTP (optional; non-blocking).
  - WhatsApp deeplink using `wa.me` to open a chat with a prefilled confirmation message (no third-party provider).

---

## 6) Admin and UI

- **Pages**
  - `/chat` – Chat UI with voice and admin buttons.
  - `/admin/customers` – Today’s bookings.
  - `/admin/db/view` – DB snapshot (tables, reservations, items).
  - `/admin/db` – Download SQLite DB.
- **Removals**
  - Disallowed views (`rooftop`, `patio`, `palo`) are purged at startup and not surfaced in UI.

---

## 7) Environment flags (`app/config.py`)

- `USE_RAG` (default: true)
- `USE_OLLAMA` (default: false)
- `OLLAMA_MODEL` (default: `llama3.1:8b` or as set via env)
- `RAG_TOP_K` (default: 3)
- SMTP (optional): `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `SMTP_FROM_NAME`

Example (PowerShell):
```powershell
$env:USE_RAG="true"
$env:USE_OLLAMA="true"
$env:OLLAMA_MODEL="llama3"
$env:SMTP_HOST="localhost"; $env:SMTP_PORT="1025"
```

---

## 8) Version matrix (tested)

- **Python**: 3.10–3.12
- **FastAPI**: 0.110+
- **SQLAlchemy**: 2.0+
- **scikit-learn**: 1.4+
- **LangChain**: 0.2.x (with `langchain-community` 0.2.x)
- **Ollama** server: 0.1.46+ (local) with models like `llama3` or `llama3.1:8b`
- **Jinja2**: 3.1+

Note: The app does not require LangChain; it’s used if available. Ollama usage is gated by `USE_OLLAMA=true`.

---

## 9) Run the app

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:
- Chat: http://127.0.0.1:8000/chat
- Customers: http://127.0.0.1:8000/admin/customers
- DB Viewer: http://127.0.0.1:8000/admin/db/view

---

## 10) Key code references

- `app/chatbot.py`
  - `handle_message()` – core intent handling and booking confirmation
  - View availability block – computes counts and lists booked customers
  - Speciality / Mains handlers – menu responses and pre-order messaging
- `app/reservation_service.py`
  - `view_stats`, `view_stats_on_date`, `view_stats_next24`
  - `list_bookings_around_view`, `list_bookings_on_date`, `list_bookings_next24_by_view`
  - `create_reservation`, `reschedule_reservation`, `cancel_reservation`
- `app/llm.py` – Ollama via LangChain adapter or REST
- `app/rag.py` – TF‑IDF retrieval
- `app/notify.py` – email + WhatsApp deeplink
- `app/models.py` – schema + seeding

---

## 11) RAG concepts (in brief)

- **Retrieval-Augmented Generation (RAG)** augments LLM responses with relevant context fetched from a knowledge store.
- This project uses a simple **TF‑IDF** vectorizer over local domain text (menu items, views, FAQs), and selects the top‑K passages by **cosine similarity**.
- The selected snippets are composed into a prompt for the LLM when general questions don’t match booking intents. This ensures domain‑grounded answers without changing booking logic.

---

## 12) Notes and future work

- Add multilingual responses (translate bot replies to user locale) while keeping internal logic in English.
- Add inline “Add x1” chips next to dishes in `chat.html` for faster pre‑order.
- Add daily digest & reminder scheduler (email or calendar invites).
- Add analytics page (by view, by hour, by capacity).

---

© Lake Serinity — All rights reserved.
