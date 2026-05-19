"""Project config loading for Worker mail."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WorkerMailConfig:
    """Cloudflare Worker mailbox settings loaded from config.json."""

    cf_worker_domain: str
    cf_email_domain: tuple[str, ...]
    cf_admin_password: str
    cf_enable_random_subdomain: bool


def project_root() -> Path:
    """Return the repository root for the installed source tree."""
    return Path(__file__).resolve().parents[2]


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load a JSON config file as a dictionary."""
    config_path = path or (project_root() / "config.json")
    try:
        with Path(config_path).open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Config file not found: {config_path}") from exc

    if not isinstance(data, dict):
        raise ValueError("config.json top-level value must be an object")
    return data


def _required_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if value is None:
        raise ValueError(f"Missing required config field: {key}")
    text = str(value).strip()
    if not text:
        raise ValueError(f"Config field must not be empty: {key}")
    return text


def _email_domains(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        domains = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        domains = [str(part).strip() for part in value]
    else:
        raise ValueError("Config field cf_email_domain must be a non-empty list or comma-separated string")

    cleaned = tuple(domain for domain in domains if domain)
    if not cleaned:
        raise ValueError("Config field cf_email_domain must not be empty")
    return cleaned


def load_worker_mail_config(path: Path | None = None) -> WorkerMailConfig:
    """Load and validate Worker mailbox settings."""
    config_path = Path(path) if path is not None else project_root() / "config.json"
    data = load_config(config_path)

    domain_value = data.get("cf_email_domain")
    if domain_value is None:
        raise ValueError("Missing required config field: cf_email_domain")

    return WorkerMailConfig(
        cf_worker_domain=_required_str(data, "cf_worker_domain").rstrip("/"),
        cf_email_domain=_email_domains(domain_value),
        cf_admin_password=_required_str(data, "cf_admin_password"),
        cf_enable_random_subdomain=bool(data.get("cf_enable_random_subdomain", True)),
    )
