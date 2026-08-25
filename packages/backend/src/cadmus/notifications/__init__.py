"""Notifications domain: polymorphic, channel-agnostic message delivery."""

from cadmus.notifications.application import NotificationService
from cadmus.notifications.domain import Notification, NotificationRecipient
from cadmus.notifications.ports import NotificationChannel, NotificationChannelError

__all__ = [
    "Notification",
    "NotificationChannel",
    "NotificationChannelError",
    "NotificationRecipient",
    "NotificationService",
]
