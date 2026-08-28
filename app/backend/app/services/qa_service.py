# E3DP backend — 站娘问答服务（设计文档 §15.2 / 决策清单 §13）
# 真实实现：DeepSeek API + 手册语义化知识库；带步骤上下文、Spine 动画关键字、AI 输出监督

from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.dynamic_settings import get_setting
from ..models import QaKnowledge, User

# 监督提示（决策清单 §13.4：System Prompt 注入自监督指令）
SUPERVISION_PROMPT = (
    "【自监督指令】请持续检查你自己的输出：若偏离本平台主题（3D打印/模型/审核/切片/费用/取件），"
    "主动纠正并引导回主题；若输出中出现违禁内容，立即停止并改为提示用户回到平台话题。"
)


def filter_words(config: dict) -> list[str]:
    return list(config.get("qa", {}).get("filter_words", []) or [])


def _hit_filter(text: str, words: list[str]) -> str | None:
    """过滤词检测：现成 Python DFA 库（如 sensitiveword）可替换本实现"""
    for w in words:
        if w and w in text:
            return w
    return None


def kb_search(db: Session, question: str, step: str) -> QaKnowledge | None:
    hits = db.query(QaKnowledge).filter_by(enabled=True).all()
    q = question.lower()
    for kb in hits:
        if any(t.lower() in q for t in (kb.keywords or [])):
            return kb
    # 步骤上下文兜底：当前步骤相关条目优先
    if step:
        for kb in hits:
            if kb.step_context and kb.step_context in step:
                return kb
    return None


def _deepseek(messages: list[dict], config: dict) -> dict:
    """调用 DeepSeek API（OpenAI 兼容）；未配置 key 时返回模拟答案，token 为估算值"""
    qa_cfg = config.get("qa", {})
    if get_setting("deepseek_api_key", settings.deepseek_api_key):
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{get_setting('deepseek_base_url', settings.deepseek_base_url)}/chat/completions",
                headers={"Authorization": f"Bearer {get_setting('deepseek_api_key', settings.deepseek_api_key)}"},
                json={"model": get_setting("deepseek_model", settings.deepseek_model), "messages": messages, "temperature": 0.7},
            )
            data = resp.json()
            usage = data.get("usage", {})
            return {
                "content": data["choices"][0]["message"]["content"],
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            }
    # 模拟（无 key / 离线演示）：按问题关键词给示例回复，token 按字符估算
    last = messages[-1]["content"] if messages else ""
    content = (
        "（模拟站娘）" + ("这个问题我大概懂了：参数零基础的同学直接选「标准档」就好，"
        "层高 0.2mm、填充 20%，质量均衡～" if "参数" in last or "档" in last else
        "我是 3D 打印小屋的站娘～有什么和打印、模型、费用、取件相关的问题都可以问我。"
        "（演示环境未配置 DeepSeek API Key，这是模拟回答）")
    )
    return {"content": content, "input_tokens": max(50, len(last) // 2), "output_tokens": max(60, len(content) // 2)}


def ask(db: Session, user: User | None, question: str, step: str, config: dict) -> dict:
    # 1) 输入过滤（双向检测之一）
    fw = _hit_filter(question, filter_words(config))
    if fw:
        return {
            "answer": "检测到输入包含敏感内容（已拦截）。本平台仅用于校园 3D 打印服务，请围绕打印主题提问～",
            "blocked": True, "animation_key": "warn", "usage": None,
        }

    # 2) 知识库命中（无需调用模型，不计费）
    kb = kb_search(db, question, step)
    if kb:
        return {"answer": kb.answer, "blocked": False, "animation_key": kb.animation_key or "happy", "kb_hit": True, "usage": None}

    # 3) 大模型回答 + 输出监督
    statement = config.get("compliance", {}).get("statement", "")
    system = (config.get("qa", {}).get("system_prompt", "") or "").format(step=step or "未指定", statement=statement)
    messages = [{"role": "system", "content": system + "\n" + SUPERVISION_PROMPT}, {"role": "user", "content": question}]
    result = _deepseek(messages, config)

    # 输出过滤：命中过滤词 → 将警示注入对话历史并重试一次
    out_fw = _hit_filter(result["content"], filter_words(config))
    if out_fw:
        messages.append({"role": "assistant", "content": result["content"]})
        messages.append({"role": "system",
                         "content": f"【监督拦截】上一条回复包含违禁内容（{out_fw}），已拦截。请重新输出：提醒用户本平台仅用于校园打印服务，并引导回主题。"})
        result = _deepseek(messages, config)

    # 4) 用量计费（决策清单 §5：按 token，不按次）
    fee = config.get("fee", {}).get("api", {})
    in_price = fee.get("deepseek_input_per_mtok", settings.deepseek_input_price_per_mtok)
    out_price = fee.get("deepseek_output_per_mtok", settings.deepseek_output_price_per_mtok)
    return {
        "answer": result["content"], "blocked": False, "animation_key": "think",
        "usage": {
            "service": "deepseek", "input_tokens": result["input_tokens"], "output_tokens": result["output_tokens"],
            "amount": round(result["input_tokens"] / 1e6 * in_price + result["output_tokens"] / 1e6 * out_price, 4),
        },
    }
