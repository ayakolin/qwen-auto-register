# Human Verification Wait State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a recoverable `waiting_human_verification` state so Web UI users can manually complete Qwen `Access Verification` in a visible browser window and have the backend resume automatically.

**Architecture:** Extend the runner with page-state detection and phase callbacks, teach the Web runtime state to expose explicit phases, and render a blocking overlay in the Web UI when manual verification is required. Keep the existing mailbox and local account flow intact after the page leaves verification mode.

**Tech Stack:** Python 3, FastAPI, Playwright sync API, standard-library `unittest`.

---

### Task 1: Runtime Phase Model

**Files:**
- Modify: `src/auto_register/web/app.py`
- Test: `tests/test_web_runtime_state.py`

- [ ] **Step 1: Write the failing test**

Add runtime-state tests that expect:

- `RuntimeState.snapshot()` includes `phase` and `phase_message`
- a new `set_phase()` method updates them while running
- `finish_run()` resets the phase to terminal state

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src /tmp/qwen-auto-register-worker-mail-venv/bin/python -m unittest tests.test_web_runtime_state -v`

Expected: FAIL because `RuntimeState` does not expose phase state yet.

- [ ] **Step 3: Write minimal implementation**

Update `RuntimeState` with:

- `phase: str`
- `phase_message: Optional[str]`
- `set_phase(phase: str, message: Optional[str] = None) -> None`

Make `start_run()` initialize `phase='running'`, `request_stop()` set `phase='stopped'`, and `finish_run()` set `phase='success'` or `phase='error'`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src /tmp/qwen-auto-register-worker-mail-venv/bin/python -m unittest tests.test_web_runtime_state -v`

Expected: PASS.

### Task 2: Runner Human Verification Detection

**Files:**
- Modify: `src/auto_register/integrations/qwen_portal.py`
- Modify: `tests/test_qwen_portal.py`

- [ ] **Step 1: Write the failing test**

Extend portal tests to cover:

- entering `waiting_human_verification` when the page body contains `Access Verification`
- resuming automatically when the page body changes to a non-verification state
- stopping while waiting returns `False`
- a closed browser/page during verification becomes a failure

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src /tmp/qwen-auto-register-worker-mail-venv/bin/python -m unittest tests.test_qwen_portal -v`

Expected: FAIL because the runner does not detect or wait through verification pages.

- [ ] **Step 3: Write minimal implementation**

Add to `QwenPortalRunner`:

- `on_phase_change` callback parameter
- helper methods for:
  - reading body text
  - detecting human verification strings
  - waiting until the page leaves verification state
- phase transitions:
  - `running`
  - `waiting_human_verification`
  - `running` on resume

For Web-driven manual verification support, force a visible browser when `on_phase_change` is provided and the runner would otherwise be headless.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src /tmp/qwen-auto-register-worker-mail-venv/bin/python -m unittest tests.test_qwen_portal -v`

Expected: PASS.

### Task 3: Web Flow Integration

**Files:**
- Modify: `src/auto_register/web/app.py`
- Test: `tests/test_web_runtime_state.py`

- [ ] **Step 1: Write the failing test**

Add a test that `_run_flow()` can receive runner phase callbacks and publish `waiting_human_verification` into `STATE`.

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src /tmp/qwen-auto-register-worker-mail-venv/bin/python -m unittest tests.test_web_runtime_state -v`

Expected: FAIL because `_run_flow()` does not wire phase callbacks into `STATE`.

- [ ] **Step 3: Write minimal implementation**

Pass `on_phase_change=lambda phase, message=None: STATE.set_phase(phase, message)` into `QwenPortalRunner` in `_run_flow()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src /tmp/qwen-auto-register-worker-mail-venv/bin/python -m unittest tests.test_web_runtime_state -v`

Expected: PASS.

### Task 4: Web UI Overlay

**Files:**
- Modify: `src/auto_register/web/app.py`

- [ ] **Step 1: Write the failing test**

There is no frontend test harness in this repo. Use a targeted rendering check instead:

- after implementation, verify the served HTML contains a verification overlay container and phase-driven client logic.

- [ ] **Step 2: Verify current failure**

Run: `rg -n "verificationOverlay|waiting_human_verification|phase_message" src/auto_register/web/app.py`

Expected: no matches for the new overlay identifiers.

- [ ] **Step 3: Write minimal implementation**

Add:

- overlay markup to the HTML shell
- styles for a blocking waiting layer
- client-side `updateStatus()` logic that shows the overlay when `phase === 'waiting_human_verification'`
- overlay text that tells the user to complete verification in the browser window and wait for automatic continuation

- [ ] **Step 4: Verify implementation**

Run: `rg -n "verificationOverlay|waiting_human_verification|phase_message" src/auto_register/web/app.py`

Expected: matches for all three identifiers.

### Task 5: Full Verification

**Files:**
- Modify: `tests/test_qwen_portal.py`
- Modify: `tests/test_web_runtime_state.py`

- [ ] **Step 1: Run full test suite**

Run: `PYTHONPATH=src /tmp/qwen-auto-register-worker-mail-venv/bin/python -m unittest discover -v`

Expected: PASS.

- [ ] **Step 2: Run import/compile checks**

Run:

```bash
PYTHONPATH=src /tmp/qwen-auto-register-worker-mail-venv/bin/python -m compileall src tests
PYTHONPATH=src /tmp/qwen-auto-register-worker-mail-venv/bin/python -c "from auto_register.integrations.qwen_portal import QwenPortalRunner; from auto_register.web.app import RuntimeState; print('import ok')"
```

Expected: both commands exit 0.

- [ ] **Step 3: Commit**

```bash
git add src/auto_register/integrations/qwen_portal.py src/auto_register/web/app.py tests/test_qwen_portal.py tests/test_web_runtime_state.py docs/superpowers/plans/2026-05-19-human-verification-wait-state.md docs/superpowers/specs/2026-05-19-qwen-human-verification-wait-state-design.md
git commit -m "feat: add human verification wait state"
```
