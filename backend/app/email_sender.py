"""Office-365 SMTP email sender for WinAgent reports."""
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
    """Send a PDF report via Office 365 SMTP.

    Reads SMTP_USER, SMTP_PASSWORD (and optionally SMTP_FROM) from env vars.
    Raises RuntimeError if credentials are missing or SMTP fails.
    """
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASSWORD", "")
    smtp_from = os.environ.get("SMTP_FROM", smtp_user)

    if not smtp_user or not smtp_pass:
        raise RuntimeError(
            "SMTP_USER und SMTP_PASSWORD müssen als Railway-Umgebungsvariablen gesetzt sein."
        )

    if not to_addresses:
        raise ValueError("Keine Empfänger angegeben")

    msg = MIMEMultipart()
    msg["From"] = smtp_from
    msg["To"] = ", ".join(to_addresses)
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
