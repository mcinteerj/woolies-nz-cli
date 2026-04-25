"""HTTP client for Woolworths API using httpx."""

import asyncio
import json
from typing import Any, Dict, Optional, cast

import httpx

from .paths import cookies_file


class CookieExpiredError(Exception):
    """Raised when cookies are expired or invalid."""

    pass


class HTTPClient:
    """Fast HTTP client for Woolworths API calls."""

    def __init__(self):
        self.cookies_file = cookies_file()
        self.base_url = "https://www.woolworths.co.nz"

    def _load_cookies(self) -> Dict[str, str]:
        """Load cookies from session file."""
        if not self.cookies_file.exists():
            raise CookieExpiredError("No saved cookies found")

        try:
            with open(self.cookies_file, "r") as f:
                cookies_list = json.load(f)

            # Convert to dict, filter to woolworths.co.nz domain
            cookies = {}
            for cookie in cookies_list:
                domain = cookie.get("domain", "")
                if "woolworths.co.nz" in domain:
                    cookies[cookie["name"]] = cookie["value"]

            if not cookies:
                raise CookieExpiredError("No valid cookies found")

            return cookies

        except (json.JSONDecodeError, KeyError) as e:
            raise CookieExpiredError(f"Invalid cookies file: {e}") from e

    def _get_xsrf_token(self, cookies: Dict[str, str]) -> Optional[str]:
        """Extract XSRF token from cookies."""
        return cookies.get("XSRF-TOKEN")

    def _get_headers(self, xsrf_token: Optional[str] = None) -> Dict[str, str]:
        """Build standard headers for API requests."""
        headers = {
            "accept": "application/json, text/plain, */*",
            "x-requested-with": "OnlineShopping.WebApp",
            "x-ui-ver": "7.70.51",
            "referer": f"{self.base_url}/",
            "origin": self.base_url,
            "user-agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            ),
        }

        if xsrf_token:
            headers["content-type"] = "application/json"
            headers["x-xsrf-token"] = xsrf_token

        return headers

    def _handle_response(
        self, response: httpx.Response, retry_on_500: bool = False
    ) -> Dict[str, Any]:
        """Handle response and provide clean error messages."""
        if response.status_code in [401, 403]:
            raise CookieExpiredError("Authentication failed - cookies expired")

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 400:
                try:
                    error_data = e.response.json()
                    message = error_data.get("message", "Invalid request")
                    raise Exception(f"Cannot process request: {message}") from e
                except json.JSONDecodeError:
                    raise Exception(
                        f"Invalid request (400): {e.response.text[:100]}"
                    ) from e
            elif status == 404:
                raise Exception("Product or resource not found (404)") from e
            elif status >= 500:
                error = Exception(
                    "Woolworths server is temporarily unavailable (500-level error)"
                )
                if retry_on_500:
                    error.retry_500 = True  # type: ignore
                raise error from e
            raise Exception(f"Woolworths API error ({status}): {e}") from e

        return cast(Dict[str, Any], response.json())

    async def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        retry_500: bool = True,
    ) -> Dict[str, Any]:
        """Make GET request to API with automatic retry on 500 errors.

        Args:
            path: API endpoint path
            params: Query parameters
            retry_500: If True, retry once on 500-level errors with exponential backoff
        """
        cookies = self._load_cookies()
        headers = self._get_headers()
        url = f"{self.base_url}{path}"
        max_attempts = 2 if retry_500 else 1
        last_exception: Optional[Exception] = None

        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        url,
                        params=params,
                        cookies=cookies,
                        headers=headers,
                        timeout=15.0,
                    )
                    return self._handle_response(response, retry_on_500=retry_500)
            except Exception as e:
                last_exception = e
                if hasattr(e, "retry_500") and attempt < max_attempts - 1:
                    wait_time = 2**attempt
                    await asyncio.sleep(wait_time)
                    continue
                raise e

        raise Exception("GET request failed after all retries") from last_exception

    async def post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make POST request to API."""
        cookies = self._load_cookies()
        xsrf_token = self._get_xsrf_token(cookies)

        if not xsrf_token:
            raise CookieExpiredError("No XSRF token found")

        headers = self._get_headers(xsrf_token)
        url = f"{self.base_url}{path}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url, json=data, cookies=cookies, headers=headers, timeout=15.0
            )
            return self._handle_response(response)

    async def delete(self, path: str) -> Dict[str, Any]:
        """Make DELETE request to API."""
        cookies = self._load_cookies()
        xsrf_token = self._get_xsrf_token(cookies)

        if not xsrf_token:
            raise CookieExpiredError("No XSRF token found")

        headers = self._get_headers(xsrf_token)
        url = f"{self.base_url}{path}"

        async with httpx.AsyncClient() as client:
            response = await client.delete(
                url, cookies=cookies, headers=headers, timeout=15.0
            )
            return self._handle_response(response)
