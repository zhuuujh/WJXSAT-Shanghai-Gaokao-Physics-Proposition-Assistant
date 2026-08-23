# -*- coding: utf-8 -*-
"""engine.provider 测试（全部 mock 网络，不触网、不计费）。"""

import json

import pytest

from engine.provider import (
    ProviderError,
    call_claude,
    call_claude_chat,
    call_deepseek,
    call_deepseek_chat,
    generate,
    generate_chat,
)


# ---------------- call_deepseek ----------------

class _FakeResp:
    def __init__(self, data_bytes):
        self._b = data_bytes

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._b

    def __getattr__(self, item):  # 兼容上下文管理的其它属性访问
        return None


def _fake_urlopen_factory(content, status=200):
    import urllib.error

    class _FakeHTTPResp(_FakeResp):
        @property
        def status(self):
            return status

    def _fake_urlopen(req, timeout=None):
        if status >= 400:
            raise urllib.error.HTTPError(req.full_url, status, "err", None, None)
        return _FakeHTTPResp(json.dumps(content).encode("utf-8"))

    return _fake_urlopen


def test_call_deepseek_success(monkeypatch):
    import engine.provider as provider_mod
    monkeypatch.setattr(provider_mod.urllib.request, "urlopen",
                        _fake_urlopen_factory({"choices": [{"message": {"content": "<p>卷子</p>"}}]}))

    out = call_deepseek("fake-key", "system", "user")
    assert out == "<p>卷子</p>"


def test_call_deepseek_http_error_raises(monkeypatch):
    import engine.provider as provider_mod
    monkeypatch.setattr(provider_mod.urllib.request, "urlopen",
                        _fake_urlopen_factory({}, status=401))

    with pytest.raises(ProviderError) as ei:
        call_deepseek("bad-key", "system", "user")
    assert "401" in str(ei.value)


def test_call_deepseek_bad_shape_raises(monkeypatch):
    import engine.provider as provider_mod
    monkeypatch.setattr(provider_mod.urllib.request, "urlopen",
                        _fake_urlopen_factory({"unexpected": 1}))

    with pytest.raises(ProviderError):
        call_deepseek("fake-key", "system", "user")


# ---------------- call_claude ----------------

class _FakeContent:
    def __init__(self, text):
        self.text = text


class _FakeResponse:
    def __init__(self, text):
        self.content = [_FakeContent(text)]


class _FakeMessages:
    def __init__(self, client):
        self._client = client

    def create(self, **kwargs):
        self._client.captured = kwargs
        return _FakeResponse("<html>claude output</html>")


class _FakeClient:
    def __init__(self, api_key=None):
        self._key = api_key
        self.captured = {}
        self.messages = _FakeMessages(self)


def test_call_claude_builds_image_part(monkeypatch):
    import anthropic
    import engine.provider as provider_mod
    client = _FakeClient()
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kw: client)

    image_data = {"media_type": "image/png", "data": "AAA"}
    out = call_claude("k", "sys", "user", image_data=image_data)
    assert out == "<html>claude output</html>"
    parts = client.captured["messages"][0]["content"]
    assert parts[0]["type"] == "image"
    assert parts[0]["source"]["data"] == "AAA"
    assert parts[1]["type"] == "text"
    assert client.captured["system"] == "sys"
    assert client.captured["model"] == provider_mod.DEFAULT_CLAUDE_MODEL


def test_call_claude_no_image(monkeypatch):
    import anthropic
    import engine.provider as provider_mod
    client = _FakeClient()
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kw: client)

    out = call_claude("k", "sys", "user")
    parts = client.captured["messages"][0]["content"]
    assert len(parts) == 1 and parts[0]["type"] == "text"
    assert out == "<html>claude output</html>"


# ---------------- generate 统一入口 ----------------

def test_generate_dispatches_deepseek(monkeypatch):
    import engine.provider as provider_mod
    monkeypatch.setattr(provider_mod, "call_deepseek",
                        lambda *a, **kw: "<p>deepseek</p>")

    html, model, ignored = generate("deepseek", "k", "sys", "user")
    assert html == "<p>deepseek</p>"
    assert model == provider_mod.DEFAULT_DEEPSEEK_MODEL
    assert ignored is False


def test_generate_deepseek_image_ignored_flag(monkeypatch):
    import engine.provider as provider_mod
    monkeypatch.setattr(provider_mod, "call_deepseek",
                        lambda *a, **kw: "<p>deepseek</p>")

    html, model, ignored = generate("deepseek", "k", "sys", "user",
                                    image_data={"media_type": "image/png", "data": "x"})
    assert ignored is True  # DeepSeek 文本模型不支持视觉


def test_generate_dispatches_claude(monkeypatch):
    import engine.provider as provider_mod
    monkeypatch.setattr(provider_mod, "call_claude",
                        lambda *a, **kw: "<p>claude</p>")

    html, model, ignored = generate("claude", "k", "sys", "user")
    assert html == "<p>claude</p>"
    assert ignored is False


def test_generate_default_provider_claude(monkeypatch):
    import engine.provider as provider_mod
    monkeypatch.setattr(provider_mod, "call_claude",
                        lambda *a, **kw: "<p>claude</p>")

    html, model, ignored = generate("", "k", "sys", "user")
    assert model == provider_mod.DEFAULT_CLAUDE_MODEL


# ---------------- call_deepseek_chat（多轮） ----------------

def test_call_deepseek_chat_builds_message_list(monkeypatch):
    import engine.provider as provider_mod

    captured = {}

    def _fake_urlopen(req, timeout=None):
        payload = json.loads(req.data.decode("utf-8"))
        captured["messages"] = payload["messages"]
        return _FakeResp(json.dumps({"choices": [{"message": {"content": "<p>新版</p>"}}]}).encode("utf-8"))

    monkeypatch.setattr(provider_mod.urllib.request, "urlopen", _fake_urlopen)

    msgs = [
        {"role": "user", "content": "改第2题"},
        {"role": "assistant", "content": "<p>上一版</p>"},
        {"role": "user", "content": "再改情境"},
    ]
    out = call_deepseek_chat("fake-key", "sys", msgs)
    assert out == "<p>新版</p>"
    sent = captured["messages"]
    assert sent[0]["role"] == "system" and sent[0]["content"] == "sys"
    assert sent[1]["role"] == "user" and sent[1]["content"] == "改第2题"
    assert sent[2]["role"] == "assistant" and sent[2]["content"] == "<p>上一版</p>"
    assert sent[3]["role"] == "user" and sent[3]["content"] == "再改情境"


# ---------------- call_claude_chat（多轮） ----------------

def test_call_claude_chat_builds_text_parts(monkeypatch):
    import anthropic
    import engine.provider as provider_mod
    client = _FakeClient()
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kw: client)

    msgs = [{"role": "user", "content": "改第1题"}]
    out = call_claude_chat("k", "sys", msgs)
    assert out == "<html>claude output</html>"
    assert client.captured["system"] == "sys"
    built = client.captured["messages"]
    assert len(built) == 1
    assert built[0]["role"] == "user"
    assert built[0]["content"][0]["type"] == "text"
    assert built[0]["content"][0]["text"] == "改第1题"


# ---------------- generate_chat 统一入口 ----------------

def test_generate_chat_dispatches_deepseek(monkeypatch):
    import engine.provider as provider_mod
    monkeypatch.setattr(provider_mod, "call_deepseek_chat",
                        lambda *a, **kw: "<p>ds chat</p>")

    text, model = generate_chat("deepseek", "k", "sys", [{"role": "user", "content": "hi"}])
    assert text == "<p>ds chat</p>"
    assert model == provider_mod.DEFAULT_DEEPSEEK_MODEL


def test_generate_chat_dispatches_claude(monkeypatch):
    import engine.provider as provider_mod
    monkeypatch.setattr(provider_mod, "call_claude_chat",
                        lambda *a, **kw: "<p>claude chat</p>")

    text, model = generate_chat("claude", "k", "sys", [{"role": "user", "content": "hi"}])
    assert text == "<p>claude chat</p>"
    assert model == provider_mod.DEFAULT_CLAUDE_MODEL


def test_generate_chat_default_provider_claude(monkeypatch):
    import engine.provider as provider_mod
    monkeypatch.setattr(provider_mod, "call_claude_chat",
                        lambda *a, **kw: "<p>claude chat</p>")

    text, model = generate_chat("", "k", "sys", [{"role": "user", "content": "hi"}])
    assert model == provider_mod.DEFAULT_CLAUDE_MODEL
