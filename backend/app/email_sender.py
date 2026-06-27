"""Email sender for WinAgent reports.

Priority:
  1. Resend API  (RESEND_API_KEY set)  — works on Railway, no SMTP port needed
  2. SMTP        (SMTP_USER + SMTP_PASSWORD set)  — for local / other environments
"""
from __future__ import annotations

import base64
import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST = "smtp.office365.com"
SMTP_PORT = 587


def send_report_email(
    to_addresses: list[str],
    subject: str,
    pdf_bytes: bytes,
    period_label: str,
    filename: str = "winagent_report.pdf",
) -> None:
    if not to_addresses:
        raise ValueError("Keine Empfänger angegeben")

    resend_key = os.environ.get("RESEND_API_KEY", "")
    if resend_key:
        _send_via_resend(resend_key, to_addresses, subject,
                         pdf_bytes, period_label, filename)
    else:
        _send_via_smtp(to_addresses, subject, pdf_bytes, period_label, filename)


# ── Resend API (recommended for Railway) ─────────────────────────────────────

def _send_via_resend(
    api_key: str,
    to_addresses: list[str],
    subject: str,
    pdf_bytes: bytes,
    period_label: str,
    filename: str,
) -> None:
    import httpx

    from_addr = os.environ.get("RESEND_FROM", "WinAgent <onboarding@resend.dev>")

    body_text = (
        f"WinAgent Bericht — Zeitraum: {period_label}\n\n"
        "Der Bericht ist als PDF-Anhang beigefügt.\n\n"
        "— WinAgent"
    )

    payload = {
        "from": from_addr,
        "to": to_addresses,
        "subject": subject,
        "text": body_text,
        "attachments": [
            {
                "filename": filename,
                "content": base64.b64encode(pdf_bytes).decode(),
            }
        ],
    }

    resp = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )

    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Resend API Fehler {resp.status_code}: {resp.text}"
        )


# ── SMTP fallback (may be blocked on Railway) ─────────────────────────────────

def _send_via_smtp(
    to_addresses: list[str],
    subject: str,
    pdf_bytes: bytes,
    period_label: str,
    filename: str,
) -> None:
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASSWORD", "")
    smtp_from = os.environ.get("SMTP_FROM", smtp_user)

    if not smtp_user or not smtp_pass:
        raise RuntimeError(
            "Kein E-Mail-Versand konfiguriert. "
            "Bitte RESEND_API_KEY (empfohlen) oder SMTP_USER + SMTP_PASSWORD "
            "als Railway-Umgebungsvariable setzen."
        )

    msg = MIMEMultipart()
    msg["From"]    = smtp_from
    msg["To"]      = ", ".join(to_addresses)
    msg["Subject"] = subject

    body_text = (
        f"WinAgent Bericht — Zeitraum: {period_label}\n\n"
        "Der Bericht ist als PDF-Anhang beigefügt.\n\n"
        "— WinAgent"
    )
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    attachment = MIMEBase("application", "pdf")
    attachment.set_payload(pdf_bytes)
    encoders.encode_base64(attachment)
    attachment.add_header(
        "Content-Disposition", f'attachment; filename="{filename}"'
    )
    msg.attach(attachment)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(smtp_user, smtp_pass)
        smtp.sendmail(smtp_from, to_addresses, msg.as_bytes())
