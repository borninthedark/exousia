"""Alert activities — email notifications."""

import os
from dataclasses import dataclass

from temporalio import activity


@dataclass
class AlertPayload:
    title: str
    body: str
    severity: str  # "critical", "warning", "info"


class AlertActivities:
    """Send alerts via SMTP."""

    @activity.defn
    async def send_email_alert(self, alert: AlertPayload) -> bool:
        """Send alert via Proton Mail SMTP."""
        try:
            import aiosmtplib
            from email.message import EmailMessage

            msg = EmailMessage()
            msg["Subject"] = f"[{alert.severity.upper()}] {alert.title}"
            msg["From"] = "info@princetonstrong.online"
            msg["To"] = "info@princetonstrong.online"
            msg.set_content(alert.body)

            await aiosmtplib.send(
                msg,
                hostname="smtp.protonmail.ch",
                port=465,
                use_tls=True,
                username="info@princetonstrong.online",
                password=os.getenv("SMTP_PASSWORD", ""),
            )
            return True
        except Exception as e:
            activity.logger.error(f"Email alert failed: {e}")
            return False
