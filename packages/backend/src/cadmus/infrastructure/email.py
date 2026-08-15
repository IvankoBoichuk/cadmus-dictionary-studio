"""SMTP delivery adapter for identity emails."""

import smtplib
from email.message import EmailMessage

from cadmus.config import Settings


class SmtpEmailSender:
    """Send verification messages without exposing credentials or tokens to logs."""

    def __init__(self, settings: Settings) -> None:
        self._host = settings.smtp_host
        self._port = settings.smtp_port
        self._username = settings.smtp_username
        self._password = settings.smtp_password
        self._sender = settings.email_from
        self._use_tls = settings.smtp_use_tls
        self._timeout = settings.smtp_timeout_seconds

    def send_verification(self, recipient: str, verification_url: str) -> None:
        message = EmailMessage()
        message["Subject"] = "Підтвердіть email для Cadmus"
        message["From"] = self._sender
        message["To"] = recipient
        message.set_content(
            "Підтвердіть реєстрацію в Cadmus, перейшовши за посиланням:\n\n"
            f"{verification_url}\n\n"
            "Посилання одноразове та має обмежений термін дії."
        )

        with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username is not None and self._password is not None:
                smtp.login(
                    self._username,
                    self._password.get_secret_value(),
                )
            smtp.send_message(message)

    def send_password_reset(self, recipient: str, reset_url: str) -> None:
        message = EmailMessage()
        message["Subject"] = "Відновлення пароля Cadmus"
        message["From"] = self._sender
        message["To"] = recipient
        message.set_content(
            "Для відновлення пароля в Cadmus перейдіть за посиланням:\n\n"
            f"{reset_url}\n\n"
            "Посилання одноразове та має обмежений термін дії. Якщо ви не "
            "надсилали цей запит, просто ігноруйте цей лист."
        )

        with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username is not None and self._password is not None:
                smtp.login(
                    self._username,
                    self._password.get_secret_value(),
                )
            smtp.send_message(message)
