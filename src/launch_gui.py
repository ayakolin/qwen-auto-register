"""PyInstaller entry point for the GUI application."""

import os
import sys
from pathlib import Path

if __name__ == "__main__":
    try:
        from dotenv import load_dotenv

        if getattr(sys, "frozen", False):
            load_dotenv(Path(sys.executable).parent / ".env")
        else:
            load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    except Exception:
        pass

    if getattr(sys, "frozen", False):
        browser_path = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browser_path)

    from auto_register.main import main

    sys.exit(main())
