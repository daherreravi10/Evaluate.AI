"""Microburbs Hackathon API client, aligned with the official one.

Matches the organisers' python-quickstart/microburbs_client.py
(github.com/David-Mib/microburbs-hackathon-demos, MIT) and the getting-started page:
- base https://api-ht.microburbs.com.au (MICROBURBS_API_BASE), key as
  "Authorization: Bearer <key>" from MICROBURBS_API_KEY (.env). Never print it.
- path is URL-encoded with quote(path, safe="/"), so "Glebe (NSW)" works as-is.
- success is {"data": ...}; "no data" is HTTP 200 {"data": null, "available": false,
  "reason", "message"} -> we return None.
- 429 and 5xx: retry, honouring Retry-After, else 1, 2, 4... s backoff.
- 403: outside the City of Sydney OR a retired address id (sales can be recorded
  against GNAF ids the current address file no longer has) -> MicroburbsError.
- ~10 requests/s per key: we throttle to config.API_RPS across threads.

Added here: a disk cache (data/cache/api/, never committed) and as-of helpers.
The API has NO as-of switch: every result used in a model goes through src.asof.

Endpoints seen in the official docs and demos (paths after /v1/):
  ping · suburbs/list · geocode/address?address= · geocode/suburb?q=
  properties/{gnaf}/profile · basics/all · sale-history · history/all
  (sale_history, rent_history, *_latest) · valuation/avm · valuation/all ·
  comparables/recent-sales-nearby · transport/nearby · amenities/nearby · risks/all
  suburbs/{name}/market/all · market/median-rent · sales/recent?limit=&offset=
  (results, total) · listings/for-sale · listings/for-rent (LIVE: after the cut-off)
Check the full list at https://api-ht.microburbs.com.au/docs with the key on the day.

python -m src.client      # smoke test: ping, suburbs, one property's history keys
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import quote

import pandas as pd
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
_session: requests.Session | None = None


class MicroburbsError(Exception):
    """An error retrying will not fix (bad key, outside the area, retired id, bad request)."""

    def __init__(self, status: int, message: str, path: str):
        super().__init__(f"HTTP {status} for {path}: {message}")
        self.status, self.message, self.path = status, message, path


def _sess() -> requests.Session:
    global _session
    if _session is None:
        key = os.environ.get("MICROBURBS_API_KEY", "")
        if not key or key == "YOUR_TEAM_KEY":
            raise RuntimeError("MICROBURBS_API_KEY not set. Copy .env.example to .env and paste the team key.")
        _session = requests.Session()
        _session.headers["Authorization"] = f"Bearer {key}"
    return _session


def _throttle() -> None:
    with _lock:
        wait = 1.0 / C.API_RPS - (time.monotonic() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.monotonic()


def _wait(resp: requests.Response, attempt: int) -> float:
    ra = resp.headers.get("Retry-After")
    if ra:
        try:
            return max(float(ra), 0.5)
        except ValueError:
            pass
    return min(2 ** attempt, 30) + random.uniform(0, 0.5)


def _message(resp: requests.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:300]
    return str(body.get("detail") or body.get("message") or body) if isinstance(body, dict) else str(body)


def get(path: str, refresh: bool = False, max_retries: int = 5, **params: Any) -> Any:
    """GET '/v1/...'; returns the unwrapped data, or None when the API has no data.
    Successful responses (including "no data") and 403s are cached on disk."""
    base = os.environ.get("MICROBURBS_API_BASE") or C.API_BASE
    url = base.rstrip("/") + quote(path, safe="/")
    h = hashlib.sha1((url + json.dumps(params, sort_keys=True)).encode()).hexdigest()
    f = CACHE_DIR / f"{h}.json"
    if f.exists() and not refresh:
        cached = json.loads(f.read_text())
        if cached.get("_status") == 403:
            raise MicroburbsError(403, cached.get("message", "outside coverage"), path)
        return cached["data"]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for attempt in range(max_retries + 1):
        _throttle()
        resp = _sess().get(url, params=params, timeout=30)
        if (resp.status_code == 429 or resp.status_code >= 500) and attempt < max_retries:
            time.sleep(_wait(resp, attempt))
            continue
        if resp.status_code == 403:
            f.write_text(json.dumps({"_status": 403, "message": _message(resp)}))
        if resp.status_code != 200:
            raise MicroburbsError(resp.status_code, _message(resp), path)
        body = resp.json()
        data = body.get("data") if isinstance(body, dict) and "data" in body else body
        f.write_text(json.dumps({"data": data}))
        return data
    raise AssertionError("unreachable")


def safe(path: str, **params: Any) -> Any:
    """Like get(), but None on 403/404 (outside area or retired id) instead of raising."""
    try:
        return get(path, **params)
    except MicroburbsError as e:
        if e.status in (403, 404):
            return None
        raise


# ---------------- endpoints ----------------

def ping():
    return get("/v1/ping")


def suburbs_list():
    return get("/v1/suburbs/list")


def geocode_address(address: str):
    return get("/v1/geocode/address", address=address)


def prop(gnaf_id: str, what: str):
    """what: profile, basics/all, sale-history, history/all, valuation/avm, ..."""
    return safe(f"/v1/properties/{gnaf_id}/{what}")


def suburb(name: str, what: str, **params):
    """name as the API writes it, e.g. 'Glebe (NSW)'; what: market/all, sales/recent, ..."""
    return safe(f"/v1/suburbs/{name}/{what}", **params)


def suburb_recent_sales(name: str, page: int = 100, max_rows: int = 20_000) -> list[dict]:
    """All pages of /suburbs/{name}/sales/recent (data: {results, total})."""
    rows, offset = [], 0
    while offset < max_rows:
        d = suburb(name, "sales/recent", limit=page, offset=offset) or {}
        res = d.get("results") or []
        rows += res
        offset += page
        if not res or offset >= (d.get("total") or 0):
            break
    return rows


def _events(items, kind: str, gnaf_id: str) -> list[dict]:
    """Normalise a history list to rows of gnaf_id, date, price, kind, type, raw keys kept."""
    out = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        date = it.get("date") or it.get("event_date") or it.get("listed_date") or it.get("sold_date")
        price = it.get("price") or it.get("weekly_rent") or it.get("rent") or it.get("amount")
        out.append({"gnaf_id": gnaf_id, "date": date, "price": price, "kind": kind,
                    "type": it.get("type") or it.get("event") or it.get("source"),
                    **{f"raw_{k}": v for k, v in it.items() if k not in ("date", "price")}})
    return out


def history(gnaf_id: str, cutoff: str | None = None) -> pd.DataFrame:
    """Sale and rent history of one property from history/all, as rows.
    With cutoff, rows dated after it are dropped (the as-of rule)."""
    d = prop(gnaf_id, "history/all") or {}
    rows = _events(d.get("sale_history"), "sale", gnaf_id) + _events(d.get("rent_history"), "rent", gnaf_id)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    if cutoff:
        df = df[df.date <= pd.Timestamp(cutoff)]
    return df


def many(fn, ids, workers: int = 6) -> dict:
    """Run fn over ids in parallel (throttled globally). Prints progress."""
    ids = list(ids)
    out, t0 = {}, time.time()
    with ThreadPoolExecutor(workers) as ex:
        for i, (k, v) in enumerate(zip(ids, ex.map(fn, ids)), 1):
            out[k] = v
            if i % 250 == 0 or i == len(ids):
                print(f"  {i:,}/{len(ids):,}  {i / (time.time() - t0):.1f}/s")
    return out


def _keys(x, depth=0):
    if isinstance(x, dict):
        return {k: _keys(v, depth + 1) if depth < 1 else type(v).__name__ for k, v in x.items()}
    if isinstance(x, list):
        return [f"{len(x)} items", _keys(x[0], depth + 1) if x else None]
    return type(x).__name__


if __name__ == "__main__":
    print("ping:", ping())
    subs = suburbs_list()
    print("suburbs:", (subs[:5] if isinstance(subs, list) else _keys(subs)))
    example = os.environ.get("EXAMPLE_GNAF", "GANSW708007997")  # flat from the official demos
    for what in ("basics/all", "sale-history", "history/all"):
        print(f"{what} keys:", json.dumps(_keys(prop(example, what)), indent=1)[:1500])
