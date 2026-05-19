"""Variable providers for email and username."""

from .one_sec_mail_provider import (
    CloudflareWorkerMailProvider,
    get_email_provider,
)
from .username_provider import UsernameProvider

__all__ = [
    "CloudflareWorkerMailProvider",
    "UsernameProvider",
    "get_email_provider",
]
