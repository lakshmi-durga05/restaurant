from __future__ import annotations
import os
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Optional
from urllib.parse import quote_plus

from . import models

SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "25"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_FROM = os.getenv("SMTP_FROM", "no-reply@lake-serinity.local")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Lake Serinity")


def _send_mail(to: str, subject: str, body: str) -> bool:
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = formataddr((SMTP_FROM_NAME, SMTP_FROM))
        msg["To"] = to
        if SMTP_USER and SMTP_PASS:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as s:
                s.starttls()
                s.login(SMTP_USER, SMTP_PASS)
                s.sendmail(SMTP_FROM, [to], msg.as_string())
        else:
            # Attempt unauthenticated localhost relay
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as s:
                s.sendmail(SMTP_FROM, [to], msg.as_string())
        return True
    except Exception:
        return False


def send_confirmation_email(reservation: models.Reservation) -> bool:
    """Best-effort: if email present, try to send a confirmation.
    Never raises; returns False if sending fails.
    """
    to = (reservation.customer_email or "").strip()
    if not to or to.lower() == "n/a":
        return False
    body = (
        f"Hello {reservation.customer_name},\n\n"
        f"Your booking is confirmed at Lake Serinity.\n"
        f"Date & Time: {reservation.reservation_time}\n"
        f"Party Size: {reservation.party_size}\n"
        f"Table: {reservation.table_id}\n\n"
        f"We look forward to serving you!\n"
        f"— Lake Serinity"
    )
    return _send_mail(to, "Your Lake Serinity Reservation is Confirmed", body)


def whatsapp_deeplink(phone: str, text: str) -> str:
    """Return a wa.me deep link the user can click to open WhatsApp with the
    message pre-filled. This does NOT send automatically; the user confirms in WhatsApp.
    Phone should be an international number digits only.
    """
    if not phone:
        phone = ""
    # Strip non-digits
    digits = "".join([c for c in phone if c.isdigit()])
    if not digits:
        # Allow link without a target phone; user can pick contact
        return f"https://wa.me/?text={quote_plus(text)}"
    return f"https://wa.me/{digits}?text={quote_plus(text)}"
