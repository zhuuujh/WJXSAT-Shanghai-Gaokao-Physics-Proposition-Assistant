# -*- coding: utf-8 -*-
"""
engine.provider —— Claude / DeepSeek 双提供商适配层。

- call_deepseek  OpenAI 兼容（urllib 直连，服务端调用，无 CORS 问题）
- call_claude    Anthropic 官方 SDK（支持图片视觉）
- generate       统一分发入口

所有网络异常统一包装为 ProviderError，UI 层据此给出友好提示。
注意：DeepSeek 文本模型不支持图片理解，"忽略图片"的警告属于 UI 职责，
本层通过 generate 返回的 used_model / is_image_ignored 告知调用方。
"""

import json
import urllib.request
import urllib.error


class ProviderError(Exception):
    """提供商调用失败（网络 / 鉴权 / 返回格式异常）。"""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


DEFAULT_CLAUDE_MODEL = "claude-sonnet-5"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
DEFAULT_MAX_TOKENS = 12000
DEFAULT_TIMEOUT = 180

_DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"


def call_deepseek(api_key, system, user_text, model=DEFAULT_DEEPSEEK_MODEL,
                  max_tokens=DEFAULT_MAX_TOKENS, timeout=DEFAULT_TIMEOUT):
    """调用 DeepSeek API（OpenAI 兼容），返回模型输出文本。

    失败（网络 / HTTP 错误 / 返回格式异常）抛 ProviderError。
    """
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": max_tokens,
        "stream": False,
    }
    req = urllib.request.Request(
        _DEEPSEEK_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ProviderError(f"DeepSeek HTTP错误 {e.code}", status=e.code) from e
    except urllib.error.URLError as e:
        raise ProviderError(f"DeepSeek 网络错误: {e.reason}") from e
    except json.JSONDecodeError as e:
        raise ProviderError(f"DeepSeek 返回格式异常: {e}") from e

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise ProviderError(f"DeepSeek 返回缺少 choices/content: {e}") from e


def call_claude(api_key, system, user_text, image_data=None, model=DEFAULT_CLAUDE_MODEL,
                max_tokens=DEFAULT_MAX_TOKENS):
    """调用 Claude API（Anthropic SDK），支持图片视觉，返回模型输出文本。

    image_data 为 {"media_type":..., "data":base64} 时，作为 type=image 的 content part
    前置发送。失败抛 ProviderError。
    """
    try:
        import anthropic
    except ImportError as e:
        raise ProviderError("未安装 anthropic SDK，请 pip install anthropic") from e

    content_parts = []
    if image_data:
        content_parts.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": image_data.get("media_type", "image/png"),
                "data": image_data.get("data", ""),
            },
        })
    content_parts.append({"type": "text", "text": user_text})

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": content_parts}],
        )
    except anthropic.APIError as e:
        raise ProviderError(f"Claude API错误: {e}") from e
    except Exception as e:
        raise ProviderError(f"Claude 调用失败: {e}") from e

    try:
        return response.content[0].text
    except (IndexError, AttributeError, TypeError) as e:
        raise ProviderError(f"Claude 返回格式异常: {e}") from e


def generate(provider, api_key, system, user_text, image_data=None):
    """统一分发入口。

    参数 provider 为 "claude" 或 "deepseek"（不区分大小写）。
    返回 (html文本, used_model, is_image_ignored)。
    is_image_ignored 为 True 表示提供了图片但该提供商不支持视觉（DeepSeek），
    UI 层据此决定是否展示"忽略图片"警告。
    """
    provider = (provider or "claude").strip().lower()
    if provider == "deepseek":
        html = call_deepseek(api_key, system, user_text)
        return html, DEFAULT_DEEPSEEK_MODEL, bool(image_data)
    return call_claude(api_key, system, user_text, image_data), DEFAULT_CLAUDE_MODEL, False


def call_deepseek_chat(api_key, system, messages, model=DEFAULT_DEEPSEEK_MODEL,
                       max_tokens=DEFAULT_MAX_TOKENS, timeout=DEFAULT_TIMEOUT):
    """调用 DeepSeek 多轮对话（OpenAI 兼容），messages 为 [{"role","content"}, ...]。"""
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}]
        + [{"role": m["role"], "content": m["content"]} for m in messages],
        "max_tokens": max_tokens,
        "stream": False,
    }
    req = urllib.request.Request(
        _DEEPSEEK_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ProviderError(f"DeepSeek HTTP错误 {e.code}", status=e.code) from e
    except urllib.error.URLError as e:
        raise ProviderError(f"DeepSeek 网络错误: {e.reason}") from e
    except json.JSONDecodeError as e:
        raise ProviderError(f"DeepSeek 返回格式异常: {e}") from e

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise ProviderError(f"DeepSeek 返回缺少 choices/content: {e}") from e


def call_claude_chat(api_key, system, messages, model=DEFAULT_CLAUDE_MODEL,
                     max_tokens=DEFAULT_MAX_TOKENS):
    """调用 Claude 多轮对话，messages 为 [{"role","content"}, ...]（纯文本）。"""
    try:
        import anthropic
    except ImportError as e:
        raise ProviderError("未安装 anthropic SDK，请 pip install anthropic") from e

    msgs = [
        {"role": m["role"], "content": [{"type": "text", "text": m["content"]}]}
        for m in messages
    ]
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=msgs,
        )
    except anthropic.APIError as e:
        raise ProviderError(f"Claude API错误: {e}") from e
    except Exception as e:
        raise ProviderError(f"Claude 调用失败: {e}") from e

    try:
        return response.content[0].text
    except (IndexError, AttributeError, TypeError) as e:
        raise ProviderError(f"Claude 返回格式异常: {e}") from e


def generate_chat(provider, api_key, system, messages):
    """多轮对话统一分发入口。

    参数 provider 为 "claude" 或 "deepseek"（不区分大小写）。
    messages 为 [{"role":"user"/"assistant","content":str}, ...]。
    返回 (文本, used_model)。
    """
    provider = (provider or "claude").strip().lower()
    if provider == "deepseek":
        return call_deepseek_chat(api_key, system, messages), DEFAULT_DEEPSEEK_MODEL
    return call_claude_chat(api_key, system, messages), DEFAULT_CLAUDE_MODEL
