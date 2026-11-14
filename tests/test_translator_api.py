import json
import threading

import pytest
import requests

from gideons_uebersetzer.translator_api import ApiError, ApiTranslator
from gideons_uebersetzer.translator_base import CancelledError


class FakeStreamResponse:
    def __init__(self, status_code=200, sse_lines=(), json_body=None, text=""):
        self.status_code = status_code
        self._lines = sse_lines
        self._json_body = json_body
        self.text = text
        self.closed = False

    def iter_lines(self, decode_unicode=False):
        yield from self._lines

    def json(self):
        if self._json_body is None:
            raise ValueError("no json")
        return self._json_body

    def close(self):
        self.closed = True


def sse(*contents):
    lines = []
    for c in contents:
        lines.append("data: " + json.dumps({"choices": [{"delta": {"content": c}}]}))
    lines.append("data: [DONE]")
    return lines


def make_translator():
    return ApiTranslator(api_key="test-key", model="mistral-small-latest",
                         endpoint="https://api.mistral.ai/v1/chat/completions")


def test_requires_api_key():
    with pytest.raises(ApiError, match="kein API-Schlüssel"):
        ApiTranslator(api_key="", model="m", endpoint="https://x")


def test_streaming_success_and_char_count(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, stream=False, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = json
        return FakeStreamResponse(200, sse("Hallo ", "Welt", "!"))

    monkeypatch.setattr(requests, "post", fake_post)
    tokens = []
    t = make_translator()
    text, chars = t.translate_stream(
        [{"role": "user", "content": "abcde"}], on_token=tokens.append
    )
    assert text == "Hallo Welt!"
    assert tokens == ["Hallo ", "Welt", "!"]
    assert chars == 5
    assert captured["payload"]["stream"] is True
    assert captured["payload"]["model"] == "mistral-small-latest"
    assert captured["headers"]["Authorization"] == "Bearer test-key"


def test_http_401_german_message(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeStreamResponse(401, json_body={"message": "bad key"}))
    with pytest.raises(ApiError, match="abgelehnt"):
        make_translator().translate([{"role": "user", "content": "x"}])


def test_http_429_and_500(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeStreamResponse(429, text="slow down"))
    with pytest.raises(ApiError, match="Zu viele Anfragen"):
        make_translator().translate([{"role": "user", "content": "x"}])
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeStreamResponse(503, text="oops"))
    with pytest.raises(ApiError, match="Serverproblem"):
        make_translator().translate([{"role": "user", "content": "x"}])


def test_timeout(monkeypatch):
    def fake_post(*a, **k):
        raise requests.Timeout("zeitüberschreitung")

    monkeypatch.setattr(requests, "post", fake_post)
    with pytest.raises(ApiError, match="Zeitüberschreitung"):
        make_translator().translate([{"role": "user", "content": "x"}])


def test_cancel_during_stream(monkeypatch):
    cancel = threading.Event()
    cancel.set()
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeStreamResponse(200, sse("Hallo")))
    with pytest.raises(CancelledError):
        make_translator().translate([{"role": "user", "content": "x"}], cancel_event=cancel)


def test_malformed_lines_skipped(monkeypatch):
    lines = ["data: kein-json", "data: " + json.dumps({"choices": []}), "", "data: " + json.dumps({"choices": [{"delta": {"content": "ok"}}]}), "data: [DONE]"]
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeStreamResponse(200, lines))
    text, _ = make_translator().translate([{"role": "user", "content": "x"}])
    assert text == "ok"
