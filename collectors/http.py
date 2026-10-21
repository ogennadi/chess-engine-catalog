"""Cached, rate-limited public HTTP requests."""

import hashlib
import json
import threading
import time
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from timestamps import utc_stamp


class ThrottledRedirects(HTTPRedirectHandler):
    def __init__(self, wait_for_slot):
        super().__init__()
        self.wait_for_slot = wait_for_slot

    def redirect_request(self, request, response, code, message, headers, new_url):
        redirected = super().redirect_request(request, response, code, message, headers, new_url)
        if redirected is not None:
            self.wait_for_slot()
        return redirected


class Fetcher:
    def __init__(self, cache_dir=Path(".cache") / "http", refresh=False, offline=False):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.refresh = refresh
        self.offline = offline
        self._lock = threading.Lock()
        self._last_request = 0.0
        self.checked_at = {}
        self.opener = build_opener(ThrottledRedirects(self._wait_for_slot))

    def _wait_for_slot(self):
        time.sleep(max(0, 1.1 - (time.monotonic() - self._last_request)))
        self._last_request = time.monotonic()

    def __call__(self, url, data=None):
        encoded = None
        if isinstance(data, dict):
            encoded = urlencode(data).encode()
        elif isinstance(data, str):
            encoded = data.encode()
        elif data is not None:
            raise TypeError("POST data must be a dictionary or string")
        key = hashlib.sha256(url.encode() + b"\0" + (encoded or b"")).hexdigest()
        cache_path = self.cache_dir / (key + ".json")
        if cache_path.exists() and not self.refresh:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            self.checked_at[url] = utc_stamp(cached["fetched_at"])
            if "http_error" in cached:
                raise HTTPError(url, cached["http_error"], cached["reason"], {}, None)
            return cached["body"]
        if self.offline:
            raise FileNotFoundError(f"No cached response for {url}")

        with self._lock:
            for attempt in range(4):
                self._wait_for_slot()
                request = Request(
                    url, data=encoded,
                    headers={"User-Agent": "chess-engine-catalog/1.0 (public chess engine catalog)"},
                )
                try:
                    with self.opener.open(request, timeout=90) as response:
                        charset = response.headers.get_content_charset() or "utf-8"
                        body = response.read().decode(charset)
                    break
                except HTTPError as error:
                    if error.code in (404, 410):
                        fetched_at = utc_stamp()
                        cache_path.write_text(json.dumps({
                            "url": url, "http_error": error.code, "reason": error.reason,
                            "fetched_at": fetched_at,
                        }), encoding="utf-8")
                        self.checked_at[url] = fetched_at
                    if error.code not in (429, 502, 503, 504) or attempt == 3:
                        raise
                    retry_after = error.headers.get("Retry-After", "")
                    if retry_after.isdigit():
                        delay = max(60, float(retry_after))
                    elif retry_after:
                        delay = max(
                            60, parsedate_to_datetime(retry_after).timestamp() - time.time()
                        )
                    else:
                        delay = 60
                    print(f"HTTP {error.code} from {url}; retrying in {delay:g}s", flush=True)
                    time.sleep(delay)
                except (TimeoutError, URLError):
                    if attempt == 3:
                        raise
                    time.sleep(5 * (attempt + 1))
            fetched_at = utc_stamp()
            cache_path.write_text(
                json.dumps({"url": url, "fetched_at": fetched_at, "body": body}),
                encoding="utf-8",
            )
            self.checked_at[url] = fetched_at
            return body
