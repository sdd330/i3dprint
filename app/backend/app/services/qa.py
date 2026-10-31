"""站娘问答（设计文档 §15 / 实现决策清单 §13）。
DeepSeek API + 知识库检索（图形化配置）+ Spine 动画关键字 + AI 输出监督：
自监督 prompt（偏离主题主动纠正）+ 敏感词过滤（DFA，输入输出双向）+ 警示注入对话历史。
用量按 token 计费（§11.3）。
"""
from __future__ import annotations

import re

import httpx
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.entities import QaConfig, QaEntry, SensitiveWord
from .cost import record_api_usage


class DFAFilter:
    """敏感词 DFA 过滤（标准实现；可按需替换为 sensitiveword 等现成库）。
    关键词表由配置中心维护（SensitiveWord 表）。"""

    def __init__(self, words: list[str]):
        self._trie: dict = {}
        for w in words:
            if not w:
                continue
            node = self._trie
            for ch in w:
                node = node.setdefault(ch, {})
            node["__end__"] = True

    def find(self, text: str) -> list[str]:
        hits: list[str] = []
        i, n = 0, len(text)
        while i < n:
            node, j = self._trie, i
            matched = None
            while j < n and text[j] in node:
                node = node[text[j]]
                j += 1
                if "__end__" in node:
                    matched = text[i:j]
            if matched:
                hits.append(matched)
                i = j
            else:
                i += 1
        return hits


def _load_filter(db: Session) -> DFAFilter | None:
    words = [w.word for w in db.query(SensitiveWord).filter_by(enabled=True).all()]
    return DFAFilter(words) if words else None


def _config(db: Session, name: str, fallback: str) -> str:
    row = db.query(QaConfig).filter_by(name=name).first()
    return row.content if row else fallback


def kb_answer(db: Session, question: str, step: str) -> QaEntry | None:
    """知识库检索：关键词命中返回条目（零 token，不计费）。"""
    entries = db.query(QaEntry).filter_by(enabled=True).all()
    q = question.lower()
    best = None
    for e in entries:
        if any(k.lower() in q for k in (e.keywords or [])):
            if e.step_context and step and step not in e.step_context:
                continue
            best = e
            break
    return best


SYSTEM_PROMPT_FALLBACK = (
    "你是校园 3D 打印自助平台 Violet Print 的站娘，名字叫薇尔莉特（英文 Violet）—— 亲切俏皮的吉祥物风格，用中文回答，自称薇尔莉特。\n"
    "平台非营利，费用只覆盖成本；打印流程为 创建需求→摆放→Val1模型审核→耗材/参数→切片→Val2切片审核→打印→Val3实物验收→费用核算。\n"
    "当前用户所在步骤：{step}。回答要结合当前步骤给情境化建议；面向参数零基础学生，语言简单清楚。\n"
    "【自监督指令】持续监测你自己的输出：如果偏离了3D打印/平台使用主题，立即在回答开头主动纠正自己并回到主题。"
)

SUPERVISION_FALLBACK = (
    "【监督提示】上一轮检测到输出中包含被拦截的内容：{words}。请忽略该内容，不要复述或讨论它，"
    "回到用户原本的问题（3D打印/平台使用），重新给出合规回答。"
)


def ask_qa(db: Session, question: str, step: str, cfg: dict) -> dict:
    qf = _load_filter(db)
    input_hits = qf.find(question) if qf else []

    hit = kb_answer(db, question, step)
    if hit:
        return {"answer": hit.answer, "animation": hit.animation_keyword or None,
                "from_kb": True, "usage": None, "supervised": bool(input_hits)}

    if not settings.deepseek_api_key:
        return {"answer": "（演示模式：未配置 DeepSeek API Key，走内置兜底回答）"
                          "这个问题手册里没有直接讲～你可以去「独立手册」翻翻，换个说法再问，或给我留言，负责人会回复你。",
                "animation": None, "from_kb": False, "usage": None, "supervised": bool(input_hits)}

    system = _config(db, "system_prompt", SYSTEM_PROMPT_FALLBACK).replace("{step}", step or "首页")
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]
    # 输入命中过滤词：直接注入警示，不让模型接触违规内容
    if input_hits:
        messages.append({"role": "system", "content": f"【监督提示】用户输入包含被拦截内容：{input_hits}。请提示用户该内容不被允许，并引导回到平台使用主题。"})

    supervised = bool(input_hits)
    for attempt in range(2):
        resp = _chat(messages)
        if resp is None:
            return {"answer": "站娘暂时走神了（服务异常），请稍后再试或留言转人工。", "animation": None,
                    "from_kb": False, "usage": None, "supervised": supervised}
        text, usage = resp
        record_api_usage(db, "qa", "deepseek", cfg, input_tokens=usage.get("prompt_tokens", 0),
                         output_tokens=usage.get("completion_tokens", 0), detail=f"step={step}")
        out_hits = qf.find(text) if qf else []
        if not out_hits:
            return {"answer": text, "animation": None, "from_kb": False, "usage": usage, "supervised": supervised}
        # 输出命中过滤词：将警示注入对话历史，重新请求（用户要求的行为）
        supervised = True
        messages.append({"role": "system", "content": _config(db, "supervision_instruction", SUPERVISION_FALLBACK)
                         .replace("{words}", ",".join(out_hits))})
        messages.append({"role": "assistant", "content": text})

    return {"answer": "（该回答涉及不适宜内容，已被拦截。）请换个话题继续问平台相关问题～",
            "animation": None, "from_kb": False, "usage": None, "supervised": True}


def _chat(messages: list[dict]) -> tuple[str, dict] | None:
    try:
        r = httpx.post(
            f"{settings.deepseek_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            json={"model": settings.deepseek_model, "messages": messages, "stream": False},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"], data.get("usage", {})
    except Exception:
        return None
