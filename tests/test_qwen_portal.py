import os
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
    def __init__(self, body_texts=None, closed=False):
        self.goto_calls = []
        self.url = ""
        self.closed = closed
        self._body_texts = list(body_texts or [])
        self._body_index = 0

    def goto(self, url, **kwargs):
        self.url = url
        self.goto_calls.append((url, kwargs))

    def wait_for_timeout(self, timeout):
        self.last_timeout = timeout

    def locator(self, selector):
        if selector == "body":
            return self
        raise AssertionError(f"Unexpected selector: {selector}")

    def inner_text(self, timeout=None):
        if not self._body_texts:
            return ""
        index = min(self._body_index, len(self._body_texts) - 1)
        value = self._body_texts[index]
        if self._body_index < len(self._body_texts) - 1:
            self._body_index += 1
        return value

    def is_closed(self):
        return self.closed


class FakeBrowser:
    def __init__(self, page):
        self.page = page
        self.closed = False

    def new_context(self, **kwargs):
        self.page.context_options = kwargs
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


class FakePatchright:
    def __init__(self, page):
        self.chromium = FakeChromium(page)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class QwenPortalRunnerTests(unittest.TestCase):
    def test_runtime_uses_patchright_sync_api(self):
        self.assertTrue(
            qwen_portal.sync_playwright.__module__.startswith("patchright."),
            qwen_portal.sync_playwright.__module__,
        )

    def test_patchright_proxy_env_names_take_priority_over_legacy_aliases(self):
        runner = qwen_portal.QwenPortalRunner()

        with patch.dict(
            os.environ,
            {
                "QWEN_PATCHRIGHT_PROXY": "http://patchright.example:7890",
                "QWEN_PLAYWRIGHT_PROXY": "http://playwright.example:7890",
                "QWEN_PATCHRIGHT_PROXY_BYPASS": "localhost,127.0.0.1",
                "QWEN_PLAYWRIGHT_PROXY_BYPASS": "legacy.local",
                "QWEN_PATCHRIGHT_PROXY_USERNAME": "patch-user",
                "QWEN_PLAYWRIGHT_PROXY_USERNAME": "legacy-user",
                "QWEN_PATCHRIGHT_PROXY_PASSWORD": "patch-pass",
                "QWEN_PLAYWRIGHT_PROXY_PASSWORD": "legacy-pass",
            },
            clear=True,
        ):
            proxy = runner._resolve_browser_proxy()

        self.assertEqual(
            proxy,
            {
                "server": "http://patchright.example:7890",
                "bypass": "localhost,127.0.0.1",
                "username": "patch-user",
                "password": "patch-pass",
            },
        )

    def test_legacy_playwright_proxy_env_names_still_work(self):
        runner = qwen_portal.QwenPortalRunner()

        with patch.dict(
            os.environ,
            {
                "QWEN_PLAYWRIGHT_PROXY": "http://legacy.example:7890",
                "QWEN_PLAYWRIGHT_PROXY_BYPASS": "legacy.local",
                "QWEN_PLAYWRIGHT_PROXY_USERNAME": "legacy-user",
                "QWEN_PLAYWRIGHT_PROXY_PASSWORD": "legacy-pass",
            },
            clear=True,
        ):
            proxy = runner._resolve_browser_proxy()

        self.assertEqual(
            proxy,
            {
                "server": "http://legacy.example:7890",
                "bypass": "legacy.local",
                "username": "legacy-user",
                "password": "legacy-pass",
            },
        )

    def test_browser_context_uses_fixed_desktop_device_options(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "accounts.txt"
            append_account = Mock(return_value=output_path)

            ok, page, _logs, _provider, _phases = self._run_with_fakes(
                append_account,
                body_texts=["The account is pending activation."],
            )

        self.assertTrue(ok)
        self.assertEqual(
            page.context_options,
            {
                "viewport": {"width": 1280, "height": 720},
                "screen": {"width": 1280, "height": 720},
                "device_scale_factor": 1,
                "is_mobile": False,
                "has_touch": False,
                "color_scheme": "light",
                "locale": "zh-CN",
            },
        )

    def test_browser_context_uses_chinese_language_and_preserves_local_time_and_location(self):
        runner = qwen_portal.QwenPortalRunner()

        context_options = runner._browser_context_options()

        self.assertEqual(context_options["locale"], "zh-CN")
        self.assertNotIn("timezone_id", context_options)
        self.assertNotIn("geolocation", context_options)
        self.assertNotIn("user_agent", context_options)

    def test_browser_context_options_are_not_randomized(self):
        runner = qwen_portal.QwenPortalRunner()

        first = runner._browser_context_options()
        second = runner._browser_context_options()

        self.assertEqual(first, second)

    def _run_with_fakes(self, append_account, *, body_texts=None, check_stop=None, enable_human_verification=False):
        page = FakePage(body_texts=body_texts)
        logs = []
        provider = FakeMailProvider()
        phases = []
        def fake_register(_self, _page, _creds):
            provider.events.append("register")

        with patch.object(qwen_portal, "get_email_provider", return_value=provider), patch.object(
            qwen_portal, "sync_playwright", return_value=FakePatchright(page)
        ), patch.object(qwen_portal, "_generate_password", return_value="Password123"), patch.object(
            qwen_portal, "append_account", append_account, create=True
        ), patch.object(qwen_portal.QwenPortalRunner, "_do_register", fake_register), patch.object(
            qwen_portal.QwenPortalRunner, "_browser_launch_options", lambda self: {"headless": True}
        ):
            runner = qwen_portal.QwenPortalRunner(
                headless=True,
                on_step=logs.append,
                check_stop=check_stop or (lambda: False),
                on_phase_change=lambda phase, message=None: phases.append((phase, message)),
                enable_human_verification=enable_human_verification,
            )
            ok = runner.run()
        return ok, page, logs, provider, phases

    def test_activation_success_appends_local_account_and_finishes(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "accounts.txt"
            append_account = Mock(return_value=output_path)

            ok, page, logs, provider, phases = self._run_with_fakes(
                append_account,
                body_texts=["The account is pending activation."],
            )

        self.assertTrue(ok)
        append_account.assert_called_once_with("new@example.com", "Password123")
        self.assertEqual(provider.events[:2], ["snapshot", "register"])
        self.assertEqual(provider.old_ids, {"old-mail"})
        self.assertIn("https://qwen.example.com/activate?token=ok", [call[0] for call in page.goto_calls])
        self.assertIn(("running", None), phases)
        self.assertTrue(any("本地账号已保存" in line for line in logs))

    def test_writer_failure_returns_false(self):
        append_account = Mock(side_effect=OSError("disk full"))

        ok, _page, logs, _provider, _phases = self._run_with_fakes(
            append_account,
            body_texts=["The account is pending activation."],
        )

        self.assertFalse(ok)
        self.assertTrue(any("本地账号写入失败" in line for line in logs))

    def test_human_verification_disabled_by_default(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "accounts.txt"
            append_account = Mock(return_value=output_path)

            ok, _page, logs, provider, phases = self._run_with_fakes(
                append_account,
                body_texts=[
                    "Access Verification Please complete the operation to verify that you are a real person",
                    "The account is pending activation. Please activate your account through the verification email in your inbox.",
                ],
            )

        self.assertTrue(ok)
        self.assertNotIn(("waiting_human_verification", None), phases)
        self.assertEqual(provider.events[-1], "wait")
        self.assertFalse(any("人工验证" in line for line in logs))

    def test_human_verification_phase_waits_then_resumes_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "accounts.txt"
            append_account = Mock(return_value=output_path)

            ok, _page, logs, provider, phases = self._run_with_fakes(
                append_account,
                body_texts=[
                    "Access Verification Please complete the operation to verify that you are a real person",
                    "The account is pending activation. Please activate your account through the verification email in your inbox.",
                ],
                enable_human_verification=True,
            )

        self.assertTrue(ok)
        self.assertIn(("waiting_human_verification", None), phases)
        self.assertGreaterEqual(phases.count(("running", None)), 2)
        self.assertEqual(provider.events[-1], "wait")
        self.assertTrue(any("人工验证" in line for line in logs))

    def test_human_verification_stop_returns_false(self):
        append_account = Mock()
        checks = iter([False, False, True])

        ok, _page, logs, provider, phases = self._run_with_fakes(
            append_account,
            body_texts=[
                "Access Verification Please complete the operation to verify that you are a real person",
                "Access Verification Please complete the operation to verify that you are a real person",
            ],
            check_stop=lambda: next(checks),
            enable_human_verification=True,
        )

        self.assertFalse(ok)
        self.assertIn(("waiting_human_verification", None), phases)
        self.assertNotIn("wait", provider.events)
        self.assertTrue(any("停止" in line for line in logs))

    def test_human_verification_closed_page_returns_false(self):
        append_account = Mock()
        page = FakePage(
            body_texts=["Access Verification Please complete the operation to verify that you are a real person"],
            closed=True,
        )
        logs = []
        provider = FakeMailProvider()
        phases = []

        def fake_register(_self, _page, _creds):
            provider.events.append("register")

        with patch.object(qwen_portal, "get_email_provider", return_value=provider), patch.object(
            qwen_portal, "sync_playwright", return_value=FakePatchright(page)
        ), patch.object(qwen_portal, "_generate_password", return_value="Password123"), patch.object(
            qwen_portal, "append_account", append_account, create=True
        ), patch.object(qwen_portal.QwenPortalRunner, "_do_register", fake_register), patch.object(
            qwen_portal.QwenPortalRunner, "_browser_launch_options", lambda self: {"headless": True}
        ):
            runner = qwen_portal.QwenPortalRunner(
                headless=True,
                on_step=logs.append,
                on_phase_change=lambda phase, message=None: phases.append((phase, message)),
                enable_human_verification=True,
            )
            ok = runner.run()

        self.assertFalse(ok)
        self.assertIn(("waiting_human_verification", None), phases)
        self.assertNotIn("wait", provider.events)


if __name__ == "__main__":
    unittest.main()
