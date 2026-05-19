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

    def test_run_flow_propagates_runner_phase_changes(self):
        state = RuntimeState()
        state.start_run()
        req = StartRequest(headless=False, loop_count=1)

        class FakeRunner:
            def __init__(self, headless, on_step, check_stop, on_phase_change):
                self._on_phase_change = on_phase_change

            def run(self):
                self._on_phase_change("waiting_human_verification", "waiting for user")
                self._on_phase_change("running", None)
                return True

        with patch.object(web_app, "STATE", state), patch.object(web_app, "QwenPortalRunner", FakeRunner), patch.object(
            state, "set_phase", wraps=state.set_phase
        ) as set_phase_mock:
            web_app._run_flow(1, req)

        self.assertTrue(
            any(call.args[0] == "waiting_human_verification" for call in set_phase_mock.call_args_list)
        )
        self.assertEqual(state.snapshot()["phase"], "success")


if __name__ == "__main__":
    unittest.main()
