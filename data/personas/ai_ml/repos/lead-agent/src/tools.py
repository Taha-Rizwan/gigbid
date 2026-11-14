"""Utility wrappers around external services."""

import os
from twilio.rest import Client

_twilio_client: Client | None = None


def _get_client() -> Client:
    """Create (or reuse) a Twilio client from environment variables."""
    global _twilio_client
    if _twilio_client is None:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        if not account_sid or not auth_token:
            raise RuntimeError("Twilio credentials not set")
        _twilio_client = Client(account_sid, auth_token)
    return _twilio_client


async def send_sms(to_number: str, body: str) -> None:
    """
    Send an SMS via Twilio.

    Parameters
    ----------
    to_number: str
        Destination phone number in E.164 format.
    body: str
        Message text.
    """
    client = _get_client()
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    if not from_number:
        raise RuntimeError("TWILIO_FROM_NUMBER not set")
    # Twilio's Python SDK is synchronous; we run it in a thread pool.
    import asyncio
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: client.messages.create(
            body=body,
            from_=from_number,
            to=to_number,
        ),
    )
