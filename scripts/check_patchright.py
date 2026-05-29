try:
    from patchright.sync_api import sync_playwright

    with sync_playwright() as p:
        print(p.chromium.executable_path or "")
except Exception:
    pass
