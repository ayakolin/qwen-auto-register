"""Qwen registration + activation runner with local account persistence."""

import os
import string
from dataclasses import dataclass
from typing import Callable, Optional

from playwright.sync_api import Page, sync_playwright

from ..providers.one_sec_mail_provider import get_email_provider
from ..providers.username_provider import UsernameProvider
from ..writer.accounts_writer import append_account


@dataclass
class QwenCredentials:
    """Credentials for a single Qwen registration."""

    username: str
    email: str
    password: str


def _generate_password(length: int = 14) -> str:
    """生成符合 Qwen 要求的密码：大小写字母+数字，≥8位。使用14位避免过长导致表单异常。"""
    import random
    # 强制包含至少各一个，满足 Qwen 要求
    pwd = [
        random.choice(string.ascii_uppercase),
        random.choice(string.ascii_lowercase),
        random.choice(string.digits),
    ]
    pwd += list(random.choices(string.ascii_letters + string.digits, k=length - 3))
    random.shuffle(pwd)
    return "".join(pwd)


class QwenPortalRunner:
    """Run simplified flow: register -> activate -> append local account."""

    REGISTER_URL = "https://chat.qwen.ai/auth?mode=register"
    HUMAN_VERIFICATION_TEXTS = (
        "access verification",
        "please complete the operation to verify that you are a real person",
    )

    def __init__(
        self,
        headless: bool = False,
        on_step: Optional[Callable[[str], None]] = None,
        check_stop: Optional[Callable[[], bool]] = None,
        on_phase_change: Optional[Callable[[str, Optional[str]], None]] = None,
    ):
        self._headless = headless
        self._headless_requested = headless
        self._on_step = on_step or (lambda _: None)
        self._check_stop = check_stop or (lambda: False)
        self._has_phase_listener = on_phase_change is not None
        self._on_phase_change = on_phase_change or (lambda _phase, _message=None: None)
        self._latest_creds: Optional[QwenCredentials] = None

    def _log(self, msg: str) -> None:
        self._on_step(msg)

    def _set_phase(self, phase: str, message: Optional[str] = None) -> None:
        self._on_phase_change(phase, message)

    def _resolve_browser_proxy(self) -> Optional[dict]:
        """Resolve Playwright proxy from env for browser automation."""
        proxy_server = (
            os.environ.get("QWEN_PLAYWRIGHT_PROXY")
            or os.environ.get("PLAYWRIGHT_PROXY")
            or os.environ.get("HTTPS_PROXY")
            or os.environ.get("HTTP_PROXY")
            or ""
        ).strip()
        if not proxy_server:
            return None

        proxy: dict = {"server": proxy_server}

        bypass = (
            os.environ.get("QWEN_PLAYWRIGHT_PROXY_BYPASS")
            or os.environ.get("NO_PROXY")
            or ""
        ).strip()
        if bypass:
            proxy["bypass"] = bypass

        username = (os.environ.get("QWEN_PLAYWRIGHT_PROXY_USERNAME") or "").strip()
        password = (os.environ.get("QWEN_PLAYWRIGHT_PROXY_PASSWORD") or "").strip()
        if username:
            proxy["username"] = username
        if password:
            proxy["password"] = password

        return proxy

    def _browser_launch_options(self) -> dict:
        """Build Chromium launch options with optional proxy support."""
        headless = self._headless
        if self._headless_requested and self._has_phase_listener:
            headless = False
            self._log("[Browser] 已启用人工验证支持，使用可见浏览器")

        options = {"headless": headless}
        proxy = self._resolve_browser_proxy()
        if proxy:
            options["proxy"] = proxy
            server = str(proxy.get("server") or "")
            self._log(f"[Browser] 已启用代理: {server}")
            bypass = str(proxy.get("bypass") or "").strip()
            if bypass:
                self._log(f"[Browser] 代理绕过列表: {bypass}")
        else:
            self._log("[Browser] 未配置 Playwright 代理，直连访问")
        return options

    def _page_body_text(self, page: Page) -> str:
        try:
            return (page.locator("body").inner_text(timeout=5000) or "").strip()
        except Exception:
            return ""

    def _is_human_verification_page(self, page: Page) -> bool:
        body_text = self._page_body_text(page).lower()
        return any(token in body_text for token in self.HUMAN_VERIFICATION_TEXTS)

    def _wait_for_human_verification(self, page: Page) -> bool:
        if not self._is_human_verification_page(page):
            return True

        self._set_phase("waiting_human_verification")
        self._log("[Portal] 检测到人工验证，请在浏览器窗口完成验证，完成后将自动继续")

        while True:
            if self._check_stop():
                self._log("[Portal] 人工验证阶段收到停止请求，结束本轮流程")
                return False

            try:
                if page.is_closed():
                    self._log("[Portal] 人工验证过程中浏览器已关闭")
                    return False
            except Exception:
                self._log("[Portal] 人工验证过程中浏览器状态不可用")
                return False

            if not self._is_human_verification_page(page):
                self._set_phase("running")
                self._log("[Portal] 人工验证已完成，继续执行")
                return True

            page.wait_for_timeout(1500)

    def run(self) -> bool:
        """Execute full flow. Returns True on success."""
        # 检查停止信号
        if self._check_stop():
            self._log("[Portal] 任务已被停止")
            return False
        self._set_phase("running")
            
        mail_provider = get_email_provider(poll_interval=5.0, timeout=120.0)
        creds = QwenCredentials(
            username=UsernameProvider().get(),
            email=mail_provider.generate_email(),
            password=_generate_password(),
        )
        self._latest_creds = creds
        self._log(f"1. 临时邮箱: {creds.email}")
        self._log(f"2. 随机密码已生成")
        old_mail_ids = mail_provider.collect_mailbox_snapshot()

        with sync_playwright() as p:
            browser = p.chromium.launch(**self._browser_launch_options())
            context = browser.new_context()
            page = context.new_page()

            try:
                # 在流程中多点检查停止信号
                if self._check_stop():
                    self._log("[Portal] 在打开浏览器后收到停止请求，放弃此次注册")
                    return False
                    
                self._do_register(page, creds)
                if not self._wait_for_human_verification(page):
                    return False
                self._log("4. 已提交注册，等待激活邮件...")
                
                if self._check_stop():
                    self._log("[Portal] 在等待邮件前收到停止请求，放弃此次注册")
                    return False
                    
                activation_url = mail_provider.wait_for_activation_link(
                    creds.email,
                    check_stop=self._check_stop,
                    old_ids=old_mail_ids,
                )
                if not activation_url:
                    self._log("[Portal] 等待邮件时收到停止请求或超时")
                    return False
                
                self._log("5. 收到激活邮件")
                
                if self._check_stop():
                    self._log("[Portal] 在激活前收到停止请求，放弃此次注册")
                    return False
                    
                page.goto(activation_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)
                self._log("6. 已打开激活链接")

                try:
                    accounts_path = append_account(creds.email, creds.password)
                except Exception as e:
                    self._log(f"7. 本地账号写入失败: {e}")
                    return False

                self._log(f"7. 本地账号已保存: {accounts_path}")
                self._log("8. 注册激活流程完成")
                return True
            except Exception as e:
                self._log(f"错误: {e}")
                raise
            finally:
                browser.close()

    def _do_register(self, page: Page, creds: QwenCredentials) -> None:
        """Fill and submit registration form."""
        self._log("3. 打开注册页并填写表单")
        page.goto(self.REGISTER_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)

        # 用户名（第一个文本输入框，或 placeholder 含「用户」）
        try:
            username_input = page.locator(
                'input[placeholder*="用户"], input[placeholder*="username"], input[name="username"], input[type="text"]'
            ).first
            username_input.wait_for(state="visible", timeout=5000)
            username_input.fill(creds.username)
        except Exception:
            pass

        # 邮箱
        email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="邮箱"]').first
        email_input.wait_for(state="visible", timeout=10000)
        email_input.fill(creds.email)

        # 密码与确认密码
        pw_inputs = page.locator('input[type="password"]')
        count = pw_inputs.count()
        if count >= 1:
            pw_inputs.nth(0).fill(creds.password)
        if count >= 2:
            pw_inputs.nth(1).fill(creds.password)

        # 勾选「我同意用户条款和隐私协议」
        try:
            # 优先：通过 label 文字定位
            label = page.locator('label').filter(has_text="我同意").first
            if label.count() > 0:
                label.click()
            else:
                # 备选：直接勾选表单中唯一的 checkbox
                cb = page.locator('input[type="checkbox"]').first
                if cb.count() > 0:
                    cb.check()
        except Exception:
            pass

        page.wait_for_timeout(800)

        # 等待提交按钮可用（填完表单并勾选协议后会解除 disabled / .disabled 类）
        submit = page.locator('button[type="submit"], button:has-text("注册"), button:has-text("Register")').first
        submit.wait_for(state="visible", timeout=5000)
        page.wait_for_function(
            """() => {
                const btn = document.querySelector('button[type=submit]');
                if (!btn) return false;
                if (btn.disabled) return false;
                if (btn.classList.contains('disabled')) return false;
                return true;
            }""",
            timeout=10000,
        )
        submit.click()
        page.wait_for_timeout(3000)
