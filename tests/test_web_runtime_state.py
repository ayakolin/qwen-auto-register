import os
import unittest
from unittest.mock import patch

import auto_register.web.app as web_app
from auto_register.web.app import RuntimeState, StartRequest


class RuntimeStateTests(unittest.TestCase):
    def test_start_run_initializes_running_phase(self):
        state = RuntimeState()

        state.start_run()
        snapshot = state.snapshot()

        self.assertEqual(snapshot["phase"], "running")
        self.assertIsNone(snapshot["phase_message"])

    def test_set_phase_updates_snapshot(self):
        state = RuntimeState()
        state.start_run()

        state.set_phase("waiting_human_verification", "waiting for user")
        snapshot = state.snapshot()

        self.assertEqual(snapshot["phase"], "waiting_human_verification")
        self.assertEqual(snapshot["phase_message"], "waiting for user")

    def test_finish_run_sets_terminal_phase(self):
        state = RuntimeState()
        state.start_run()
        state.set_phase("waiting_human_verification", "waiting for user")

        state.finish_run(ok=False, error="failed")
        snapshot = state.snapshot()

        self.assertEqual(snapshot["phase"], "error")
        self.assertEqual(snapshot["phase_message"], "failed")

    def test_run_flow_does_not_require_phase_callback(self):
        state = RuntimeState()
        state.start_run()
        req = StartRequest(headless=False, loop_count=1)

        class FakeRunner:
            def __init__(self, headless, on_step, check_stop):
                self.headless = headless

            def run(self):
                return True

        with patch.object(web_app, "STATE", state), patch.object(web_app, "QwenPortalRunner", FakeRunner):
            web_app._run_flow(1, req)

        self.assertEqual(state.snapshot()["phase"], "success")

    def test_run_flow_keeps_proxy_env_when_request_has_no_proxy(self):
        state = RuntimeState()
        state.start_run()
        req = StartRequest(headless=False, loop_count=1)

        class FakeRunner:
            def __init__(self, headless, on_step, check_stop):
                pass

            def run(self):
                return True

        original = {key: os.environ.get(key) for key in (
            "QWEN_PATCHRIGHT_PROXY",
            "QWEN_PATCHRIGHT_PROXY_USERNAME",
            "QWEN_PATCHRIGHT_PROXY_PASSWORD",
            "QWEN_PATCHRIGHT_PROXY_BYPASS",
        )}
        os.environ["QWEN_PATCHRIGHT_PROXY"] = "http://127.0.0.1:8080"
        os.environ["QWEN_PATCHRIGHT_PROXY_USERNAME"] = "user"
        os.environ["QWEN_PATCHRIGHT_PROXY_PASSWORD"] = "pass"
        os.environ["QWEN_PATCHRIGHT_PROXY_BYPASS"] = "localhost"
        observed = {}
        try:
            with patch.object(web_app, "STATE", state), patch.object(web_app, "QwenPortalRunner", FakeRunner):
                web_app._run_flow(1, req)
                observed = {key: os.environ.get(key) for key in (
                    "QWEN_PATCHRIGHT_PROXY",
                    "QWEN_PATCHRIGHT_PROXY_USERNAME",
                    "QWEN_PATCHRIGHT_PROXY_PASSWORD",
                    "QWEN_PATCHRIGHT_PROXY_BYPASS",
                )}
        finally:
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.assertEqual(observed["QWEN_PATCHRIGHT_PROXY"], "http://127.0.0.1:8080")
        self.assertEqual(observed["QWEN_PATCHRIGHT_PROXY_USERNAME"], "user")
        self.assertEqual(observed["QWEN_PATCHRIGHT_PROXY_PASSWORD"], "pass")
        self.assertEqual(observed["QWEN_PATCHRIGHT_PROXY_BYPASS"], "localhost")

    def test_run_flow_sets_patchright_proxy_env_from_request(self):
        state = RuntimeState()
        state.start_run()
        req = StartRequest(
            headless=False,
            loop_count=1,
            proxy_server="http://127.0.0.1:7897",
            proxy_username="user",
            proxy_password="pass",
            proxy_bypass="localhost",
        )

        class FakeRunner:
            def __init__(self, headless, on_step, check_stop):
                pass

            def run(self):
                return True

        keys = (
            "QWEN_PATCHRIGHT_PROXY",
            "QWEN_PATCHRIGHT_PROXY_USERNAME",
            "QWEN_PATCHRIGHT_PROXY_PASSWORD",
            "QWEN_PATCHRIGHT_PROXY_BYPASS",
            "QWEN_PLAYWRIGHT_PROXY",
            "QWEN_PLAYWRIGHT_PROXY_USERNAME",
            "QWEN_PLAYWRIGHT_PROXY_PASSWORD",
            "QWEN_PLAYWRIGHT_PROXY_BYPASS",
        )
        original = {key: os.environ.get(key) for key in keys}
        for key in keys:
            os.environ.pop(key, None)

        try:
            with patch.object(web_app, "STATE", state), patch.object(web_app, "QwenPortalRunner", FakeRunner):
                web_app._run_flow(1, req)

            self.assertEqual(os.environ.get("QWEN_PATCHRIGHT_PROXY"), "http://127.0.0.1:7897")
            self.assertEqual(os.environ.get("QWEN_PATCHRIGHT_PROXY_USERNAME"), "user")
            self.assertEqual(os.environ.get("QWEN_PATCHRIGHT_PROXY_PASSWORD"), "pass")
            self.assertEqual(os.environ.get("QWEN_PATCHRIGHT_PROXY_BYPASS"), "localhost")
            self.assertIsNone(os.environ.get("QWEN_PLAYWRIGHT_PROXY"))
            self.assertIsNone(os.environ.get("QWEN_PLAYWRIGHT_PROXY_USERNAME"))
            self.assertIsNone(os.environ.get("QWEN_PLAYWRIGHT_PROXY_PASSWORD"))
            self.assertIsNone(os.environ.get("QWEN_PLAYWRIGHT_PROXY_BYPASS"))
        finally:
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
