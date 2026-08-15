"""SMTP adapter contract against the isolated Mailpit service."""

import os
import urllib.request

import pytest
from cadmus.config import Environment, Settings
from cadmus.infrastructure.email import SmtpEmailSender

pytestmark = pytest.mark.integration


def test_verification_email_is_delivered_with_the_one_time_link() -> None:
    settings = Settings(
        environment=Environment.TEST,
        smtp_host=os.environ["CADMUS_TEST_SMTP_HOST"],
        smtp_port=1025,
    )
    verification_url = "https://cadmus.example/verify-email#token=integration-token"

    SmtpEmailSender(settings).send_verification(
        "integration-user@example.com",
        verification_url,
    )

    with urllib.request.urlopen(
        f"{os.environ['CADMUS_TEST_MAILPIT_URL']}/view/latest.txt",
        timeout=5,
    ) as response:
        delivered_message = response.read().decode("utf-8")

    assert verification_url in delivered_message
