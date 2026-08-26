"""Unit tests for the polymorphic notification channels."""

import smtplib

import httpx
import pytest
from cadmus.config import Settings
from cadmus.infrastructure.notifications import (
    GmailNotificationChannel,
    TelegramNotificationChannel,
)
from cadmus.notifications import (
    Notification,
    NotificationChannelError,
    NotificationRecipient,
    NotificationService,
)
from pydantic import SecretStr


class _FakeChannel:
    """A channel whose behavior a test controls directly."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[NotificationRecipient, Notification]] = []

    def send(
        self, recipient: NotificationRecipient, notification: Notification
    ) -> None:
        self.calls.append((recipient, notification))
        if self.fail:
            raise NotificationChannelError("boom")


def _notification() -> Notification:
    return Notification(subject="subj", body="body")


def _recipient() -> NotificationRecipient:
    return NotificationRecipient(email="owner@example.com", telegram_chat_id="42")


def test_notification_service_sends_through_every_channel() -> None:
    gmail = _FakeChannel()
    telegram = _FakeChannel()
    service = NotificationService(channels=[gmail, telegram])

    failed = service.notify(_recipient(), _notification())

    assert failed == []
    assert gmail.calls == [(_recipient(), _notification())]
    assert telegram.calls == [(_recipient(), _notification())]


def test_notification_service_is_polymorphic_over_channel_type() -> None:
    """The service only relies on ``NotificationChannel.send`` -- any object
    implementing it works, regardless of concrete type (Gmail, Telegram, or
    a test double)."""
    channels: list[object] = [_FakeChannel(), _FakeChannel()]
    service = NotificationService(channels=channels)  # type: ignore[arg-type]

    failed = service.notify(_recipient(), _notification())

    assert failed == []


def test_notification_service_keeps_going_after_one_channel_fails() -> None:
    broken = _FakeChannel(fail=True)
    healthy = _FakeChannel()
    service = NotificationService(channels=[broken, healthy])

    failed = service.notify(_recipient(), _notification())

    assert failed == ["_FakeChannel"]
    assert healthy.calls  # the healthy channel still ran


def test_gmail_channel_skips_recipient_with_no_email() -> None:
    channel = GmailNotificationChannel(Settings())
    recipient = NotificationRecipient(email=None, telegram_chat_id="42")

    channel.send(recipient, _notification())  # must not raise or connect


def test_gmail_channel_wraps_smtp_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_args: object, **_kwargs: object) -> None:
        raise smtplib.SMTPConnectError(421, "no route")

    monkeypatch.setattr(smtplib, "SMTP", _raise)
    channel = GmailNotificationChannel(Settings())

    with pytest.raises(NotificationChannelError):
        channel.send(_recipient(), _notification())


def test_telegram_channel_skips_recipient_with_no_chat_id() -> None:
    channel = TelegramNotificationChannel(
        Settings(telegram_bot_token=SecretStr("test-token"))
    )
    recipient = NotificationRecipient(email="owner@example.com", telegram_chat_id=None)

    channel.send(recipient, _notification())  # must not raise or call the API


def test_telegram_channel_skips_when_no_bot_token_configured() -> None:
    channel = TelegramNotificationChannel(Settings(telegram_bot_token=None))

    channel.send(_recipient(), _notification())  # must not raise


def test_telegram_channel_sends_via_bot_api(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _fake_post(
        url: str, *, json: dict[str, object], timeout: float
    ) -> httpx.Response:
        captured["url"] = url
        captured["json"] = json
        return httpx.Response(
            200, json={"ok": True}, request=httpx.Request("POST", url)
        )

    monkeypatch.setattr(httpx, "post", _fake_post)
    channel = TelegramNotificationChannel(
        Settings(telegram_bot_token=SecretStr("test-token"))
    )

    channel.send(_recipient(), _notification())

    assert captured["url"] == "https://api.telegram.org/bottest-token/sendMessage"
    assert captured["json"] == {"chat_id": "42", "text": "subj\n\nbody"}


def test_telegram_channel_wraps_http_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_post(*_args: object, **_kwargs: object) -> httpx.Response:
        raise httpx.ConnectError("no route", request=httpx.Request("POST", "https://x"))

    monkeypatch.setattr(httpx, "post", _fake_post)
    channel = TelegramNotificationChannel(
        Settings(telegram_bot_token=SecretStr("test-token"))
    )

    with pytest.raises(NotificationChannelError):
        channel.send(_recipient(), _notification())
