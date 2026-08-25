"""Notification domain objects.

Deliberately dumb: a ``Notification`` is just text, and a
``NotificationRecipient`` is just addresses. Turning an app-level event
(e.g. "dictionary scan finished") into this shape is the caller's job, not
this module's -- keeps ``notifications`` a dependency-free leaf, the same
role ``geography`` plays for reference data.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Notification:
    """A channel-agnostic message to deliver."""

    subject: str
    body: str


@dataclass(frozen=True)
class NotificationRecipient:
    """Where a notification may be delivered, per channel.

    A field left ``None`` means the caller has no address for that channel;
    channels treat that as "nothing to do here", not a failure.
    """

    email: str | None = None
    telegram_chat_id: str | None = None
