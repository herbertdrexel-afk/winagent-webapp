"""Email sender for WinAgent reports.

Priority:
  1. Microsoft Graph API  (MS_TENANT_ID + MS_CLIENT_ID + MS_CLIENT_SECRET set)
  2. Resend API           (RESEND_API_KEY set)
  3. SMTP                 (SMTP_USER + SMTP_PASSWORD set)  — may be blocked on Railway
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

    ms_tenant = os.environ.get("MS_TENANT_ID", "")
    ms_client = os.environ.get("MS_CLIENT_ID", "")
    ms_secret = os.environ.get("MS_CLIENT_SECRET", "")
    resend_key = os.environ.get("RESEND_API_KEY", "")

    if ms_tenant and ms_client and ms_secret:
        _send_via_graph(ms_tenant, ms_client, ms_secret,
                        to_addresses, subject, pdf_bytes, period_label, filename)
    elif resend_key:
        _send_via_resend(resend_key, to_addresses, subject,
                         pdf_bytes, period_label, filename)
    else:
        _send_via_smtp(to_addresses, subject, pdf_bytes, period_label, filename)


# ── Microsoft Graph API ───────────────────────────────────────────────────────

def _send_via_graph(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    to_addresses: list[str],
    subject: str,
    pdf_bytes: bytes,
    period_label: str,
    filename: str,
) -> None:
    import httpx

    sender = os.environ.get("MS_SENDER_EMAIL", "")
    if not sender:
        raise RuntimeError(
            "MS_SENDER_EMAIL muss als Railway-Umgebungsvariable gesetzt sein "
            "(z.B. h.drexel@nagroup.biz)"
        )

    # 1. OAuth2 client-credentials token
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    token_resp = httpx.post(token_url, data={
        "grant_type":    "client_credentials",
        "client_id":     client_id,
        "client_secret": client_secret,
        "scope":         "https://graph.microsoft.com/.default",
    }, timeout=20)
    if token_resp.status_code != 200:
        raise RuntimeError(
            f"Graph-Token Fehler {token_resp.status_code}: {token_resp.text}"
        )
    access_token = token_resp.json()["access_token"]

    body_text = (
        f"WinAgent Bericht — Zeitraum: {period_label}\n\n"
        "Der Bericht ist als PDF-Anhang beigefügt.\n\n"
        "— WinAgent"
    )

    # 2. Send mail via Graph
    mail_payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body_text},
            "toRecipients": [
                {"emailAddress": {"address": addr}} for addr in to_addresses
            ],
            "attachments": [
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": filename,
                    "contentType": "application/pdf",
                    "contentBytes": base64.b64encode(pdf_bytes).decode(),
                }
            ],
        },
        "saveToSentItems": "true",
    }

    send_url = f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail"
    send_resp = httpx.post(
        send_url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type":  "application/json",
        },
        json=mail_payload,
        timeout=30,
    )
    # Graph returns 202 Accepted on success
    if send_resp.status_code not in (200, 201, 202):
        raise RuntimeError(
            f"Graph sendMail Fehler {send_resp.status_code}: {send_resp.text}"
        )


# ── Resend API (fallback, works on Railway) ───────────────────────────────────

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
            "Bitte MS_TENANT_ID + MS_CLIENT_ID + MS_CLIENT_SECRET (empfohlen) "
            "oder RESEND_API_KEY oder SMTP_USER + SMTP_PASSWORD setzen."
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
