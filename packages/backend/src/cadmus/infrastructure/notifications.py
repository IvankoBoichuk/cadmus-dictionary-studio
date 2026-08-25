"""Concrete ``NotificationChannel`` adapters: SMTP (Gmail) and Telegram."""

import smtplib
from email.message import EmailMessage

import httpx

from cadmus.config import Settings
from cadmus.notifications.domain import Notification, NotificationRecipient
from cadmus.notifications.ports import NotificationChannelError

_TELEGRAM_API_BASE_URL = "https://api.telegram.org"


class GmailNotificationChannel:
    """Deliver notifications over SMTP (Gmail's SMTP relay or any other).

    Reuses the same ``CADMUS_SMTP_*`` settings as the identity module's
    ``SmtpEmailSender`` -- one configured mailbox, two adapters, because
    identity's sender speaks in verification/reset templates while this one
    speaks in generic subject/body notifications.
    """

    def __init__(self, settings: Settings) -> None:
        self._host = settings.smtp_host
        self._port = settings.smtp_port
        self._username = settings.smtp_username
        self._password = settings.smtp_password
        self._sender = settings.email_from
        self._use_tls = settings.smtp_use_tls
        self._timeout = settings.smtp_timeout_seconds

    def send(
        self, recipient: NotificationRecipient, notification: Notification
    ) -> None:
        if recipient.email is None:
            return

        message = EmailMessage()
        message["Subject"] = notification.subject
        message["From"] = self._sender
        message["To"] = recipient.email
        message.set_content(notification.body)

        try:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
                if self._use_tls:
                    smtp.starttls()
                if self._username is not None and self._password is not None:
                    smtp.login(self._username, self._password.get_secret_value())
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as error:
            raise NotificationChannelError("gmail delivery failed") from error


class TelegramNotificationChannel:
    """Deliver notifications through a Telegram bot's ``sendMessage`` call."""

    def __init__(self, settings: Settings) -> None:
        self._bot_token = settings.telegram_bot_token
        self._timeout = settings.telegram_timeout_seconds

    def send(
        self, recipient: NotificationRecipient, notification: Notification
    ) -> None:
        if recipient.telegram_chat_id is None or self._bot_token is None:
            return

        token = self._bot_token.get_secret_value()
        url = f"{_TELEGRAM_API_BASE_URL}/bot{token}/sendMessage"
        text = f"{notification.subject}\n\n{notification.body}"
        try:
            response = httpx.post(
                url,
                json={"chat_id": recipient.telegram_chat_id, "text": text},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise NotificationChannelError("telegram delivery failed") from error
