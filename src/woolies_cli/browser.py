"""Browser session management with auto-login for Woolworths NZ.

Uses Camoufox (Firefox-based anti-detect browser) for ARM64 compatibility
and Akamai bot detection bypass.
"""

import json
import os
from typing import Optional

from camoufox.async_api import AsyncCamoufox

from .config import ConfigError, load_credentials
from .paths import cookies_file, screenshot_file, state_dir, storage_file


class AuthError(Exception):
    """Authentication failed."""

    pass


class BrowserSession:
    """Manages Camoufox browser with auto-login.

    Camoufox is a Firefox-based anti-detect browser that:
    - Works on ARM64 Linux (pre-built binaries)
    - Bypasses Akamai bot detection via fingerprint spoofing
    - Has Playwright-compatible API
    """

    def __init__(self, headless: bool = True, slow_mo: int = 0):
        self.headless = headless
        self.slow_mo = slow_mo
        self._camoufox: Optional[AsyncCamoufox] = None
        self._browser = None
        self._context = None

        self.session_dir = state_dir()
        self.cookies_file = cookies_file()
        self.storage_file = storage_file()  # Legacy, kept for debugging

    async def __aenter__(self):
        """Enter context manager - launch browser and return page."""
        proxy_url = os.getenv("WOOLIES_PROXY")
        proxy_config = {"server": proxy_url} if proxy_url else None

        self._camoufox = AsyncCamoufox(
            headless=self.headless,
            proxy=proxy_config,
        )

        self._browser = await self._camoufox.__aenter__()

        contexts = self._browser.contexts
        if contexts:
            self._context = contexts[0]
        else:
            self._context = await self._browser.new_context()

        await self._load_session()

        page = await self._context.new_page()

        if self.slow_mo > 0:
            page._slow_mo = self.slow_mo

        return page

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - save session and close browser."""
        if self._context:
            await self._save_session()

        if self._camoufox:
            await self._camoufox.__aexit__(exc_type, exc_val, exc_tb)

    async def is_logged_in(self, page) -> bool:
        """Check if currently logged in by looking for sign-in link."""
        await page.goto("https://www.woolworths.co.nz")
        await page.wait_for_timeout(3000)

        try:
            await page.wait_for_selector(
                'a:has-text("Sign in")', timeout=5000, state="visible"
            )
            return False
        except Exception:
            return True

    async def login(self, page) -> None:
        """Perform 2-step login flow."""
        try:
            email, password = load_credentials()
        except ConfigError as e:
            raise AuthError(str(e)) from e

        await page.goto("https://www.woolworths.co.nz")
        await page.wait_for_timeout(2000)

        try:
            await page.wait_for_selector(
                'a:has-text("Sign in")', timeout=10000, state="visible"
            )
            await page.click('a:has-text("Sign in")')
        except Exception as e:
            raise AuthError(f"Could not find sign-in link: {e}") from e

        try:
            await page.wait_for_url(
                lambda url: "auth" in url or "login" in url, timeout=15000
            )
            await page.wait_for_load_state("networkidle")

            await page.wait_for_selector(
                'input[type="email"], input[name="username"]', timeout=20000
            )
            email_input = await page.query_selector(
                'input[type="email"]'
            ) or await page.query_selector('input[name="username"]')
            if email_input:
                await email_input.fill(email)
                await email_input.press("Enter")
                await page.wait_for_timeout(3000)
            else:
                await page.screenshot(path=str(screenshot_file("login_failed_email")))
                raise AuthError("Could not find email input field")
        except AuthError:
            raise
        except Exception as e:
            await page.screenshot(path=str(screenshot_file("login_failed_exception")))
            raise AuthError(f"Email step failed: {e}") from e

        try:
            await page.wait_for_selector(
                'input[type="password"]:visible', timeout=10000
            )
            password_input = await page.query_selector('input[type="password"]:visible')
            if password_input:
                await password_input.fill(password)
                await password_input.press("Enter")
            else:
                raise AuthError("Could not find password input field")
        except AuthError:
            raise
        except Exception as e:
            raise AuthError(f"Password step failed: {e}") from e

        try:
            await page.wait_for_url("https://www.woolworths.co.nz/**", timeout=15000)
        except Exception:
            pass

        await page.wait_for_timeout(2000)

    async def ensure_logged_in(self, page) -> None:
        """Ensure logged in, auto-login if needed."""
        if not await self.is_logged_in(page):
            await self.login(page)

    async def _load_session(self) -> None:
        """Load saved cookies if they exist."""
        if not self._context:
            return

        if self.cookies_file.exists():
            try:
                with open(self.cookies_file, "r") as f:
                    cookies = json.load(f)

                woolies_cookies = []
                for cookie in cookies:
                    domain = cookie.get("domain", "")
                    if "woolworths.co.nz" in domain:
                        woolies_cookies.append(
                            {
                                "name": cookie["name"],
                                "value": cookie["value"],
                                "domain": cookie.get("domain", ".woolworths.co.nz"),
                                "path": cookie.get("path", "/"),
                                "expires": cookie.get("expires", -1),
                                "httpOnly": cookie.get("httpOnly", False),
                                "secure": cookie.get("secure", True),
                                "sameSite": cookie.get("sameSite", "Lax"),
                            }
                        )

                if woolies_cookies:
                    await self._context.add_cookies(woolies_cookies)
            except Exception:
                pass

    async def _save_session(self) -> None:
        """Save cookies to disk."""
        if not self._context:
            return

        self.session_dir.mkdir(parents=True, exist_ok=True)

        try:
            cookies = await self._context.cookies()
            with open(self.cookies_file, "w") as f:
                json.dump(cookies, f, indent=2)
        except Exception:
            pass

        try:
            storage = await self._context.storage_state()
            with open(self.storage_file, "w") as f:
                json.dump(storage, f, indent=2)
        except Exception:
            pass
