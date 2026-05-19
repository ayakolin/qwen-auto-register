"""Local email:password account file writer."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from ..config import load_worker_mail_config


_WRITE_LOCK = threading.Lock()


def append_account(email: str, password: str, path: Optional[str | Path] = None) -> Path:
    """Append one account line and return the file path."""
    email = (email or "").strip()
    password = password or ""
    if not email:
        raise ValueError("email must not be empty")

    output_path = Path(path) if path is not None else load_worker_mail_config().accounts_file
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with _WRITE_LOCK:
        with output_path.open("a", encoding="utf-8") as f:
            f.write(f"{email}:{password}\n")
    return output_path
