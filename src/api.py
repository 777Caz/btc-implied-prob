"""
Small HTTP helpers shared by all fetchers: one place for timeouts, retries and polite pacing.
"""
import logging
import time

import requests

import config

log = logging.getLogger(__name__)

SESSION = requests.Session()


def get_json(url: str, params: dict | None = None, *, retries: int = 4, pause: float = 0.2):
    """GET a URL and return parsed JSON. Retries on network errors, 429 and 5xx with backoff.

    `pause` is a short sleep after every successful call so bulk backfills stay well under
    each API's public rate limit.
    """
    for attempt in range(retries + 1):
        try:
            resp = SESSION.get(url, params=params, timeout=30)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise requests.HTTPError(f"HTTP {resp.status_code}", response=resp)
            resp.raise_for_status()
            time.sleep(pause)
            return resp.json()
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
            status = getattr(e.response, "status_code", None)
            retryable = status is None or status == 429 or status >= 500
            if not retryable or attempt == retries:
                raise
            wait = 2 ** attempt
            log.warning("Request failed (%s), retrying in %ds: %s", e, wait, url)
            time.sleep(wait)


def deribit(method: str, base: str = config.DERIBIT_BASE, **params):
    """Call a public Deribit JSON-RPC method over HTTP GET and return its `result` field.

    Deribit wraps every response as {"jsonrpc": "2.0", "result": ...} or {"error": {...}}.
    Pass base=config.DERIBIT_HISTORY_BASE for trades older than 24 hours.
    """
    data = get_json(f"{base}/public/{method}", params=params, pause=0.1)
    if "error" in data:
        raise RuntimeError(f"Deribit {method} error: {data['error']}")
    return data["result"]
