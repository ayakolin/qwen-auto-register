"""Cloudflare Worker temporary email provider."""

from __future__ import annotations

import html
import json
import random
import re
import string
import time
from pathlib import Path
from typing import Any, Callable, Optional

import httpx

from ..config import WorkerMailConfig, load_worker_mail_config


def get_email_provider(
    poll_interval: float = 5.0,
    timeout: float = 120.0,
):
    """Return the active Worker mailbox provider."""
    return CloudflareWorkerMailProvider(poll_interval=poll_interval, timeout=timeout)


def _extract_activation_url_from_text(text: str) -> Optional[str]:
    """Extract the first likely Qwen activation URL from mail content."""
    url_pattern = r"https://[^\s<>\"']+"
    urls = [html.unescape(url).rstrip(").,;") for url in re.findall(url_pattern, text or "")]
    for url in urls:
        lower = url.lower()
        if any(kw in lower for kw in ("verify", "activate", "confirm", "token", "auth")):
            return url
    return urls[0] if urls else None


def _mailbox_name() -> str:
    """Generate a codexoauthloop-style random mailbox local part."""
    name_len = random.randint(10, 14)
    chars = list(random.choices(string.ascii_lowercase, k=name_len))
    for _ in range(random.choice([1, 2])):
        pos = random.randint(2, len(chars) - 1)
        chars.insert(pos, random.choice(string.digits))
    return "".join(chars)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(_as_text(item) for item in value if item is not None)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _sender_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("address") or value.get("email") or value.get("name") or "").strip()
    return _as_text(value).strip()


def _normalize_mail_item(item: dict[str, Any]) -> dict[str, str]:
    """Normalize a Worker mail item to id/subject/source/raw fields."""
    subject = _as_text(item.get("subject")).strip()
    source = (
        _sender_text(item.get("source"))
        or _sender_text(item.get("from"))
        or _sender_text(item.get("sender"))
    )
    mail_id = _as_text(item.get("id") or item.get("message_id") or item.get("uid")).strip()

    raw = _as_text(item.get("raw")).strip()
    if not raw:
        body = (
            _as_text(item.get("body"))
            or _as_text(item.get("html_body"))
            or _as_text(item.get("htmlBody"))
            or _as_text(item.get("html"))
            or _as_text(item.get("textBody"))
            or _as_text(item.get("text"))
            or _as_text(item.get("content"))
        )
        raw = f"Subject: {subject}\nFrom: {source}\n\n{body or ''}"

    return {
        "id": mail_id,
        "subject": subject,
        "source": source,
        "raw": raw,
    }


def _mail_item_id(item: dict[str, str]) -> str:
    """Return a stable-ish mail identity for snapshot polling."""
    mail_id = item.get("id")
    if mail_id:
        return str(mail_id)
    return "|".join(
        [
            item.get("subject", "")[:80],
            item.get("source", "")[:80],
            item.get("raw", "")[:120],
        ]
    )


def _mail_items_from_response(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []

    candidates = [
        data.get("results"),
        data.get("mails"),
        data.get("items"),
        data.get("list"),
    ]
    nested = data.get("data")
    if isinstance(nested, list):
        candidates.append(nested)
    elif isinstance(nested, dict):
        candidates.extend(
            [
                nested.get("results"),
                nested.get("mails"),
                nested.get("items"),
                nested.get("list"),
            ]
        )

    for candidate in candidates:
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    return []


class CloudflareWorkerMailProvider:
    """Temporary email provider using the Cloudflare Worker API."""

    def __init__(
        self,
        poll_interval: float = 5.0,
        timeout: float = 120.0,
        config: WorkerMailConfig | None = None,
        client_factory: Callable[..., Any] = httpx.Client,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._poll_interval = poll_interval
        self._timeout = timeout
        self._config = config or load_worker_mail_config()
        self._client_factory = client_factory
        self._sleep = sleep
        self._email: Optional[str] = None
        self._token: Optional[str] = None

    def generate_email(self) -> str:
        """Create a temporary mailbox and return its address."""
        url = f"https://{self._config.cf_worker_domain}/admin/new_address"
        payload = {
            "enablePrefix": True,
            "enableRandomSubdomain": self._config.cf_enable_random_subdomain,
            "name": _mailbox_name(),
            "domain": random.choice(self._config.cf_email_domain),
        }
        headers = {
            "x-admin-auth": self._config.cf_admin_password,
            "Content-Type": "application/json",
        }

        with self._client_factory(timeout=30.0, verify=False) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        address = str(data.get("address") or "").strip()
        token = str(data.get("jwt") or "").strip()
        if not address or not token:
            raise RuntimeError(f"Worker mailbox creation response missing address or jwt: {data}")

        self._email = address
        self._token = token
        return address

    def fetch_emails(self) -> list[dict[str, str]]:
        """Fetch and normalize the current Worker inbox."""
        if not self._token:
            raise ValueError("CloudflareWorkerMailProvider: call generate_email first")

        url = f"https://{self._config.cf_worker_domain}/api/mails"
        headers = {"Authorization": f"Bearer {self._token}"}
        with self._client_factory(timeout=30.0, verify=False) as client:
            resp = client.get(url, params={"limit": 10, "offset": 0}, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        return [_normalize_mail_item(item) for item in _mail_items_from_response(data)]

    def _collect_mailbox_snapshot(self) -> set[str]:
        return {_mail_item_id(item) for item in self.fetch_emails()}

    def wait_for_activation_link(
        self,
        email: str,
        subject_contains: Optional[str] = None,
        from_contains: Optional[str] = None,
        check_stop: Optional[Callable[[], bool]] = None,
    ) -> str:
        """Poll new Worker mail until an activation link is found."""
        if email != self._email or not self._token:
            raise ValueError("CloudflareWorkerMailProvider: must wait on the generated email address")

        if check_stop and check_stop():
            return ""

        seen_ids = self._collect_mailbox_snapshot()
        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            if check_stop and check_stop():
                return ""

            for item in self.fetch_emails():
                mail_id = _mail_item_id(item)
                if mail_id in seen_ids:
                    continue
                seen_ids.add(mail_id)

                subject = item.get("subject", "").lower()
                source = item.get("source", "").lower()
                if subject_contains and subject_contains.lower() not in subject:
                    continue
                if from_contains and from_contains.lower() not in source:
                    continue

                url = _extract_activation_url_from_text(item.get("raw", ""))
                if url:
                    return url

            self._sleep(self._poll_interval)

        raise TimeoutError(f"No activation email within {self._timeout}s for {email}")


__all__ = [
    "CloudflareWorkerMailProvider",
    "get_email_provider",
    "_extract_activation_url_from_text",
    "_normalize_mail_item",
]
