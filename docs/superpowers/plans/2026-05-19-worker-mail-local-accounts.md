# Worker Mail Local Accounts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the active temp-mail flow with the Cloudflare Worker mail flow used by `codexoauthloop`, stop after Qwen email activation, and append successful `email:password` records locally.

**Architecture:** Add a small project config loader for `config.json`, replace the temp-mail provider with a Worker-only provider, add a focused local accounts writer, and simplify `QwenPortalRunner` so activation plus local write is the success boundary. Keep Web/GUI entry points intact while updating labels and docs.

**Tech Stack:** Python 3, standard-library `unittest`, `httpx`, Playwright sync API.

---

### Task 1: Config Loader

**Files:**
- Create: `src/auto_register/config.py`
- Create: `tests/test_config.py`
- Create: `config.json`

- [ ] **Step 1: Write failing config tests**

Add `tests/test_config.py` covering successful load, missing required field, and project-root path resolution.

- [ ] **Step 2: Run tests to verify failure**

Run: `/tmp/qwen-auto-register-worker-mail-venv/bin/python -m unittest tests.test_config -v`

Expected: FAIL because `src.auto_register.config` does not exist.

- [ ] **Step 3: Implement config loader**

Create `src/auto_register/config.py` with:

- `project_root() -> Path`
- `load_config(path: Path | None = None) -> dict[str, Any]`
- `load_worker_mail_config(path: Path | None = None) -> WorkerMailConfig`
- `WorkerMailConfig` dataclass containing `cf_worker_domain`, `cf_email_domain`, `cf_admin_password`, `cf_enable_random_subdomain`, `accounts_file`

- [ ] **Step 4: Add placeholder config**

Create `config.json` with placeholder Worker fields and no real secrets.

- [ ] **Step 5: Run config tests**

Run: `/tmp/qwen-auto-register-worker-mail-venv/bin/python -m unittest tests.test_config -v`

Expected: PASS.

### Task 2: Worker Mail Provider

**Files:**
- Modify: `src/auto_register/providers/one_sec_mail_provider.py`
- Create: `tests/test_worker_mail_provider.py`

- [ ] **Step 1: Write failing provider tests**

Add tests for:

- Worker email creation POST path, headers, and body.
- Worker mail normalization from common Worker response shapes.
- Snapshot-based polling skips old mail and returns a link from new mail.
- Stop callback returns an empty string before timeout.

- [ ] **Step 2: Run tests to verify failure**

Run: `/tmp/qwen-auto-register-worker-mail-venv/bin/python -m unittest tests.test_worker_mail_provider -v`

Expected: FAIL because the provider still uses Mail.tm / 1secMail / old Cloud Mail behavior.

- [ ] **Step 3: Replace provider implementation**

Rewrite the module around `CloudflareWorkerMailProvider`:

- `get_email_provider()` always returns `CloudflareWorkerMailProvider`.
- `generate_email()` calls `POST https://{cf_worker_domain}/admin/new_address`.
- `fetch_emails()` calls `GET https://{cf_worker_domain}/api/mails` with the mailbox JWT.
- `_mail_item_id()`, `_normalize_mail_item()`, `_collect_mailbox_snapshot()`, and `wait_for_activation_link()` implement codexoauthloop-style snapshot polling.
- `_extract_activation_url_from_text()` keeps the existing activation-link preference rules.

- [ ] **Step 4: Run provider tests**

Run: `/tmp/qwen-auto-register-worker-mail-venv/bin/python -m unittest tests.test_worker_mail_provider -v`

Expected: PASS.

### Task 3: Local Accounts Writer

**Files:**
- Create: `src/auto_register/writer/accounts_writer.py`
- Create: `tests/test_accounts_writer.py`

- [ ] **Step 1: Write failing writer tests**

Add tests for appending one account, appending multiple accounts without overwrite, and creating parent directories.

- [ ] **Step 2: Run tests to verify failure**

Run: `/tmp/qwen-auto-register-worker-mail-venv/bin/python -m unittest tests.test_accounts_writer -v`

Expected: FAIL because `accounts_writer.py` does not exist.

- [ ] **Step 3: Implement writer**

Create `append_account(email: str, password: str, path: str | Path | None = None) -> Path`.

When `path` is omitted, load `accounts_file` from `config.json`. Always append exactly one `email:password\n` line.

- [ ] **Step 4: Run writer tests**

Run: `/tmp/qwen-auto-register-worker-mail-venv/bin/python -m unittest tests.test_accounts_writer -v`

Expected: PASS.

### Task 4: Portal Flow Simplification

**Files:**
- Modify: `src/auto_register/integrations/qwen_portal.py`
- Create: `tests/test_qwen_portal.py`

- [ ] **Step 1: Write failing portal tests**

Add tests using fake provider, fake Playwright, and fake writer to verify:

- Activation success appends the local account and returns `True`.
- The remote auth method is never called after activation.
- Writer failure is surfaced as a failed run.

- [ ] **Step 2: Run tests to verify failure**

Run: `/tmp/qwen-auto-register-worker-mail-venv/bin/python -m unittest tests.test_qwen_portal -v`

Expected: FAIL because the current runner still calls remote proxy auth.

- [ ] **Step 3: Update portal flow**

Remove active imports and calls for `get_qwen_auth_url`, `list_auth_files`, and `poll_auth_status`. After opening the activation link, call `append_account(creds.email, creds.password)`, log the local file path, and return `True`.

- [ ] **Step 4: Run portal tests**

Run: `/tmp/qwen-auto-register-worker-mail-venv/bin/python -m unittest tests.test_qwen_portal -v`

Expected: PASS.

### Task 5: UI and Docs

**Files:**
- Modify: `README.md`
- Modify: `ARCHITECTURE.md`
- Modify: `.env.example`
- Modify: `src/auto_register/web/app.py`
- Modify: `src/auto_register/gui/app.py`

- [ ] **Step 1: Update user-facing text**

Change active-flow wording to "register, activate, local save"; remove provider dropdown behavior that suggests Mail.tm / 1secMail / LuckMail support.

- [ ] **Step 2: Update docs**

Document `config.json`, Cloudflare Worker mail requirements, and `accounts.txt` output. Remove remote CLI Proxy API from the active flow.

- [ ] **Step 3: Run full test suite**

Run: `/tmp/qwen-auto-register-worker-mail-venv/bin/python -m unittest discover -v`

Expected: PASS.

- [ ] **Step 4: Run import checks**

Run:

```bash
/tmp/qwen-auto-register-worker-mail-venv/bin/python -m compileall src tests
/tmp/qwen-auto-register-worker-mail-venv/bin/python -c "from auto_register.integrations.qwen_portal import QwenPortalRunner; from auto_register.providers.one_sec_mail_provider import get_email_provider; print('import ok')"
```

Expected: both commands exit 0.
