import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from auto_register.integrations import qwen_portal


class FakeMailProvider:
    def __init__(self, activation_url="https://qwen.example.com/activate?token=ok"):
        self.activation_url = activation_url
        self.events = []

    def generate_email(self):
        return "new@example.com"

    def collect_mailbox_snapshot(self):
        self.events.append("snapshot")
        return {"old-mail"}

    def wait_for_activation_link(self, email, check_stop=None, old_ids=None):
        self.waited_email = email
        self.old_ids = old_ids
        self.events.append("wait")
        return self.activation_url


class FakePage:
    def __init__(self):
        self.goto_calls = []
        self.url = ""

    def goto(self, url, **kwargs):
        self.url = url
        self.goto_calls.append((url, kwargs))

    def wait_for_timeout(self, timeout):
        self.last_timeout = timeout


class FakeBrowser:
    def __init__(self, page):
        self.page = page
        self.closed = False

    def new_context(self):
        return self

    def new_page(self):
        return self.page

    def close(self):
        self.closed = True


class FakeChromium:
    def __init__(self, page):
        self.page = page

    def launch(self, **kwargs):
        self.launch_options = kwargs
        return FakeBrowser(self.page)


class FakePlaywright:
    def __init__(self, page):
        self.chromium = FakeChromium(page)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class QwenPortalRunnerTests(unittest.TestCase):
    def _run_with_fakes(self, append_account):
        page = FakePage()
        logs = []
        remote_auth = Mock(return_value=True)
        provider = FakeMailProvider()
        def fake_register(_self, _page, _creds):
            provider.events.append("register")

        with patch.object(qwen_portal, "get_email_provider", return_value=provider), patch.object(
            qwen_portal, "sync_playwright", return_value=FakePlaywright(page)
        ), patch.object(qwen_portal, "_generate_password", return_value="Password123"), patch.object(
            qwen_portal, "append_account", append_account, create=True
        ), patch.object(qwen_portal.QwenPortalRunner, "_do_register", fake_register), patch.object(
            qwen_portal.QwenPortalRunner, "_browser_launch_options", lambda self: {"headless": True}
        ), patch.object(
            qwen_portal.QwenPortalRunner, "_run_remote_proxy_link_auth", remote_auth, create=True
        ):
            runner = qwen_portal.QwenPortalRunner(headless=True, on_step=logs.append)
            ok = runner.run()
        return ok, page, logs, remote_auth, provider

    def test_activation_success_appends_local_account_and_finishes(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "accounts.txt"
            append_account = Mock(return_value=output_path)

            ok, page, logs, remote_auth, provider = self._run_with_fakes(append_account)

        self.assertTrue(ok)
        append_account.assert_called_once_with("new@example.com", "Password123")
        self.assertFalse(remote_auth.called)
        self.assertEqual(provider.events[:2], ["snapshot", "register"])
        self.assertEqual(provider.old_ids, {"old-mail"})
        self.assertIn("https://qwen.example.com/activate?token=ok", [call[0] for call in page.goto_calls])
        self.assertTrue(any("本地账号已保存" in line for line in logs))

    def test_writer_failure_returns_false(self):
        append_account = Mock(side_effect=OSError("disk full"))

        ok, _page, logs, remote_auth, _provider = self._run_with_fakes(append_account)

        self.assertFalse(ok)
        self.assertFalse(remote_auth.called)
        self.assertTrue(any("本地账号写入失败" in line for line in logs))


if __name__ == "__main__":
    unittest.main()
