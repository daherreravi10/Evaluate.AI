"""The API client against a fake server: auth, encoding, retries, no-data, 403, cache, as-of."""
import json

import pytest

from src import client, config as C


class Resp:
    def __init__(self, status, body, headers=None):
        self.status_code, self._body, self.headers = status, body, headers or {}
        self.text = json.dumps(body)

    def json(self):
        return self._body


@pytest.fixture
def fake(monkeypatch, tmp_path):
    monkeypatch.setenv("MICROBURBS_API_KEY", "test-key")
    monkeypatch.setattr(client, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(client, "_session", None)
    monkeypatch.setattr(client.time, "sleep", lambda s: None)
    calls, queue = [], {}

    def get(self, url, params=None, timeout=None):
        calls.append((url, params, self.headers.get("Authorization")))
        return queue[url].pop(0)

    monkeypatch.setattr(client.requests.Session, "get", get)
    return calls, queue


def test_bearer_encoding_retry_and_unwrap(fake):
    calls, queue = fake
    url = C.API_BASE + "/v1/suburbs/Glebe%20%28NSW%29/market/median-rent"
    queue[url] = [Resp(429, {}, {"Retry-After": "1"}), Resp(200, {"data": {"unit": 800}})]
    assert client.suburb("Glebe (NSW)", "market/median-rent") == {"unit": 800}
    assert len(calls) == 2 and calls[0][2] == "Bearer test-key"
    # cached: no third call
    assert client.suburb("Glebe (NSW)", "market/median-rent") == {"unit": 800}
    assert len(calls) == 2


def test_no_data_is_none_and_403_is_none_with_safe(fake):
    _, queue = fake
    a = C.API_BASE + "/v1/properties/G1/history/all"
    b = C.API_BASE + "/v1/properties/G2/history/all"
    queue[a] = [Resp(200, {"data": None, "available": False, "reason": "x", "message": "y"})]
    queue[b] = [Resp(403, {"detail": "outside area"})]
    assert client.prop("G1", "history/all") is None
    assert client.prop("G2", "history/all") is None
    with pytest.raises(client.MicroburbsError):
        client.get("/v1/properties/G2/history/all")  # cached 403 still raises in get()


def test_history_rows_and_cutoff(fake):
    _, queue = fake
    u = C.API_BASE + "/v1/properties/G3/history/all"
    queue[u] = [Resp(200, {"data": {
        "sale_history": [{"date": "2020-03-01", "price": 700000, "type": "Sold"},
                         {"date": "2026-09-15", "price": 820000, "type": "Sold"}],
        "rent_history": [{"date": "2026-07-01", "price": 750}]}})]
    df = client.history("G3", cutoff="2026-08-31")
    assert sorted(df.kind) == ["rent", "sale"]
    assert df.date.max().strftime("%Y-%m-%d") == "2026-07-01"
