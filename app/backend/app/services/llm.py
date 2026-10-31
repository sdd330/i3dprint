# Violet Print backend — AI 对话客户端（通用 OpenAI 兼容端点）
# ---------------------------------------------------------------------------
# 2026-10 用户要求：AI 对话不再绑定 DeepSeek，改成"通用 API endpoint"，并且能
# 获取模型列表、切换模型。
#   · Endpoint：任意 OpenAI 兼容 /v1（LM Studio / Ollama / DeepSeek / OpenAI / vLLM…）
#   · 模型：GET {base}/models 列出来（自动过滤 embedding 模型），PUT 切换后即时生效
#   · 兼容：llm_* 未配置时回退旧的 deepseek_* 设置
#   · 本地服务不走 http_proxy（trust_env=False），否则 127.0.0.1 会被代理拦截

from __future__ import annotations

import re

import httpx

from ..core.config import settings
from ..core.dynamic_settings import get_setting

# 推理型模型（qwen3 / deepseek-r1 等）会输出 <think> 推理段，回答前先剥离
_THINK_BLOCK = re.compile(r"<\s*(think|reasoning)\s*>.*?<\s*/\s*\1\s*>", re.S | re.I)
_THINK_OPEN = re.compile(r"^\s*<\s*(think|reasoning)\s*>.*", re.S | re.I)


_EMOJI = re.compile(
    "["
    "\U0001F000-\U0001FAFF"   # 各类 emoji / 图形符号
    "\U00002600-\U000027BF"   # 杂项符号 & 装饰
    "\U0001F1E6-\U0001F1FF"   # 国旗
    "\U00002B00-\U00002BFF"
    "\U0000FE0F"               # variation selector
    "\U0000200D"               # ZWJ
    "\U000023E9-\U000023FA"
    "]+"
)


def strip_emoji(text: str) -> str:
    """去掉 emoji（本项目 UI 规范：全站不使用 emoji）。"""
    if not text:
        return ""
    return _EMOJI.sub("", text).replace("  ", " ").strip()


def strip_reasoning(text: str) -> str:
    """去掉 <think>…</think> 之类的推理块（留给人看的只有结论）。"""
    if not text:
        return ""
    out = _THINK_BLOCK.sub("", text)
    if _THINK_OPEN.match(out):
        # 没有闭合标签：整体视为推理，按空处理
        out = ""
    return out.strip()


# 模型列表里排除这些（它们只能做 embedding，不能对话）
_EMBED_HINTS = ("embedding", "bge", "text2vec", "gte-", "e5-", "rerank")


def llm_conf() -> dict:
    """当前生效的对话端点/密钥/模型（通用 OpenAI 兼容，2026-10 起不再有 DeepSeek 专用配置）。"""
    return {
        "base_url": (get_setting("llm_base_url", settings.llm_base_url) or "").strip().rstrip("/"),
        "api_key": (get_setting("llm_api_key", settings.llm_api_key) or "").strip(),
        "model": (get_setting("llm_model", settings.llm_model) or "").strip(),
    }


# ---- 并发闸门：本地模型（LM Studio）通常一次只跑一个请求，必须排队，否则互相拖死 ----
import threading as _threading

_sem_lock = _threading.Lock()
_sem: _threading.BoundedSemaphore | None = None
_sem_size = 0
_waiting = 0
_running = 0


def _limits() -> tuple[int, int]:
    from ..core.config import settings as st
    size = max(1, int(get_setting("llm_max_concurrent", st.llm_max_concurrent)))
    timeout = max(5, int(get_setting("llm_queue_timeout_sec", st.llm_queue_timeout_sec)))
    return size, timeout


def _semaphore() -> _threading.BoundedSemaphore:
    """按当前配置并发上限懒创建信号量（改设置后自动重建）。"""
    global _sem, _sem_size
    size, _ = _limits()
    with _sem_lock:
        if _sem is None or _sem_size != size:
            _sem = _threading.BoundedSemaphore(size)
            _sem_size = size
        return _sem


def queue_stats() -> dict:
    size, timeout = _limits()
    return {"max_concurrent": size, "running": _running, "waiting": _waiting, "queue_timeout_sec": timeout}


def _client() -> httpx.Client:
    return httpx.Client(timeout=90, trust_env=False)


def _headers(conf: dict) -> dict:
    h = {"Content-Type": "application/json"}
    if conf.get("api_key"):
        h["Authorization"] = f"Bearer {conf['api_key']}"
    return h


def is_chat_model(model_id: str) -> bool:
    m = (model_id or "").lower()
    return bool(m) and not any(h in m for h in _EMBED_HINTS)


def list_models(conf: dict | None = None) -> dict:
    """GET {base}/models → {reachable, models:[{id}], chat_models:[id], error?}"""
    conf = conf or llm_conf()
    out = {"base_url": conf["base_url"], "reachable": False, "models": [], "chat_models": []}
    if not conf["base_url"]:
        out["error"] = "未配置 Endpoint"
        return out
    try:
        with _client() as c:
            r = c.get(f"{conf['base_url']}/models", headers=_headers(conf))
            r.raise_for_status()
            ids = [m.get("id", "") for m in r.json().get("data", []) if m.get("id")]
        out.update(reachable=True, models=ids, chat_models=[i for i in ids if is_chat_model(i)])
    except Exception as e:  # 网络/鉴权问题：把原因带回管理端
        out["error"] = f"{type(e).__name__}: {str(e)[:160]}"
    return out


def resolve_model(conf: dict | None = None) -> str:
    """当前要用的模型：配置值优先；否则从 /models 里挑第一个对话模型。"""
    conf = conf or llm_conf()
    if conf["model"]:
        return conf["model"]
    info = list_models(conf)
    return (info["chat_models"] or info["models"] or [""])[0]


def chat(messages: list[dict], *, temperature: float = 0.7, model: str | None = None,
         timeout_ms: int | None = None) -> dict | None:
    """调用 /chat/completions（带并发闸门）。

    成功返回 {content, input_tokens, output_tokens, model, queued_ms}；
    排队超时返回 {error: "queue_timeout", ...}；其他失败返回 None。
    """
    global _waiting, _running
    conf = llm_conf()
    if not conf["base_url"]:
        return None
    use_model = model or resolve_model(conf)
    if not use_model:
        return None
    size, queue_timeout = _limits()
    wait_timeout = (timeout_ms / 1000.0) if timeout_ms else float(queue_timeout)

    sem = _semaphore()
    import time as _time
    t0 = _time.time()
    _waiting += 1
    acquired = sem.acquire(timeout=wait_timeout)
    _waiting -= 1
    if not acquired:
        return {"error": "queue_timeout", "queued_ms": int((_time.time() - t0) * 1000),
                "queue": queue_stats()}
    queued_ms = int((_time.time() - t0) * 1000)
    _running += 1
    try:
        payload = {"model": use_model, "messages": messages, "temperature": temperature, "stream": False}
        with _client() as c:
            r = c.post(f"{conf['base_url']}/chat/completions", headers=_headers(conf), json=payload)
            r.raise_for_status()
            data = r.json()
    except Exception:
        return None
    finally:
        _running -= 1
        sem.release()
    choices = data.get("choices") or []
    if not choices:
        return None
    usage = data.get("usage") or {}
    content = (choices[0].get("message") or {}).get("content") or ""
    return {
        "content": strip_emoji(strip_reasoning(content)),
        "input_tokens": usage.get("prompt_tokens") or max(1, sum(len(m.get("content", "")) for m in messages) // 2),
        "output_tokens": usage.get("completion_tokens") or max(1, len(content) // 2),
        "model": data.get("model") or use_model,
        "queued_ms": queued_ms,
    }
