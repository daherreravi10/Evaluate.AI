"""Cached Microburbs Hackathon API client.

- Base URL https://api-ht.microburbs.com.au, key as a Bearer token from
  MICROBURBS_API_KEY (.env). Never print or commit the key.
- ~10 requests/s per key: we throttle to API_RPS and back off on 429.
- "No data" is still HTTP 200 with {"data": null, "available": false}.
- Outside the City of Sydney returns 403.
- Every response is cached under data/cache/api/ so nothing is fetched twice.
- The API has NO as-of switch: always pass results through src.asof.until().
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

import requests

from . import config as C

try:
    from dotenv import load_dotenv
    load_dotenv(C.ROOT / ".env")
except ImportError:
    pass

CACHE_DIR = C.CACHE / "api"
_lock = threading.Lock()
_last = [0.0]


def _key() -> str:
    k = os.environ.get("MICROBURBS_API_KEY", "")
    if not k:
        raise RuntimeError("MICROBURBS_API_KEY not set. Copy .env.example to .env and paste the team key.")
    return k


def _throttle() -> None:
    with _lock:
        wait = 1.0 / C.API_RPS - (time.monotonic() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.monotonic()


def get(path: str, params: dict | None = None, refresh: bool = False, retries: int = 5):
    """GET a path like '/v1/properties/GANSW.../sale-history'. Returns parsed JSON,
    {'_status': 403} outside coverage, or None when the API says no data."""
    url = C.API_BASE + path
    h = hashlib.sha1((url + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
    f = CACHE_DIR / f"{h}.json"
    if f.exists() and not refresh:
        return json.loads(f.read_text())
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for attempt in range(retries):
        _throttle()
        r = requests.get(url, params=params, timeout=30,
                         headers={"Authorization": f"Bearer {_key()}"})
        if r.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 403:
            out = {"_status": 403}
            break
        r.raise_for_status()
        out = r.json()
        break
    else:
        raise RuntimeError(f"429 after {retries} retries: {path}")
    f.write_text(json.dumps(out))
    return out


def data(resp):
    """Unwrap {'data': ...}; None when unavailable."""
    if resp is None or (isinstance(resp, dict) and (resp.get("_status") == 403 or resp.get("available") is False)):
        return None
    return resp.get("data", resp) if isinstance(resp, dict) else resp


def sale_history(gnaf_id: str):
    return data(get(f"/v1/properties/{gnaf_id}/sale-history"))


def rent_history(gnaf_id: str):
    return data(get(f"/v1/properties/{gnaf_id}/rent-history"))


def suburb(name: str, what: str):
    return data(get(f"/v1/suburbs/{quote(name)}/{what}"))


def many(fn, ids, workers: int = 6) -> dict:
    """Run fn over ids in parallel (still throttled globally). Print progress."""
    out, t0 = {}, time.time()
    with ThreadPoolExecutor(workers) as ex:
        for i, (k, v) in enumerate(zip(ids, ex.map(fn, ids)), 1):
            out[k] = v
            if i % 500 == 0:
                print(f"  {i:,}/{len(ids):,}  {i / (time.time() - t0):.1f}/s")
    return out


if __name__ == "__main__":
    # smoke test on the day: python -m src.client
    print(json.dumps(get("/v1/suburbs/list"), indent=1)[:800])
