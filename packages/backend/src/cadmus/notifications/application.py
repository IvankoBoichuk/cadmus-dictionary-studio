"""Fan a notification out across every configured channel."""

import logging
from collections.abc import Sequence

from cadmus.notifications.domain import Notification, NotificationRecipient
from cadmus.notifications.ports import NotificationChannel, NotificationChannelError

logger = logging.getLogger(__name__)


class NotificationService:
    """Send one notification through every channel it was given.

    Channels are polymorphic (``NotificationChannel.send``): the service
    does not know or care whether a channel is email, Telegram, or anything
    added later. One channel failing (bad Telegram token, SMTP timeout)
    never stops the others -- delivery is best-effort per channel, and
    failures are logged, not raised, mirroring how the OCR scan queue
    treats one bad page.
    """

    def __init__(self, channels: Sequence[NotificationChannel]) -> None:
        self._channels = channels

    def notify(
        self, recipient: NotificationRecipient, notification: Notification
    ) -> list[str]:
        """Send to every channel; return the names of channels that failed."""
        failed: list[str] = []
        for channel in self._channels:
            channel_name = type(channel).__name__
            try:
                channel.send(recipient, notification)
            except NotificationChannelError:
                logger.warning(
                    "notification channel %s failed to deliver", channel_name
                )
                failed.append(channel_name)
        return failed
