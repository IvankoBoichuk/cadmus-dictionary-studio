"""Application-owned ports for notification infrastructure."""

from typing import Protocol

from cadmus.notifications.domain import Notification, NotificationRecipient


class NotificationChannelError(Exception):
    """A channel could not deliver a notification it was asked to send.

    Raised only for an actual delivery failure (transport/API error) with a
    usable recipient address -- a channel with no address for the recipient
    (e.g. no ``telegram_chat_id``) returns normally instead, since that is
    an absent channel, not a failed one.
    """


class NotificationChannel(Protocol):
    """One polymorphic delivery mechanism (email, Telegram, ...)."""

    def send(
        self, recipient: NotificationRecipient, notification: Notification
    ) -> None: ...
