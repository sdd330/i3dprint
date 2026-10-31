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
    "【格式要求】不要使用任何 emoji 或表情符号；不要使用 Markdown 标题/表格符号，用简体中文分点回答。\n"
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


def kb_search(db: Session, question: str, step: str, strong: bool = True) -> QaKnowledge | None:
    """关键词条目命中。

    强命中（strong=True）：命中长度 ≥3 的关键词，或命中 ≥2 个关键词——
      这类通常是平台专属问题（活动密码、取件、自备耗材），优先于教材作答。
    弱命中（strong=False）：只命中 1 个两字关键词（如「填充」「耗材」）——
      不抢教材的位置，只在教材也没命中时兜底。
    """
    hits = db.query(QaKnowledge).filter_by(enabled=True).all()
    q = question.lower()
    for kb in hits:
        matched = [t for t in (kb.keywords or []) if t and t.lower() in q]
        if not matched:
            continue
        if strong:
            if max(len(t) for t in matched) >= 3 or len(matched) >= 2:
                return kb
        else:
            return kb
    if strong and step:
        for kb in hits:
            if kb.step_context and kb.step_context in step and len(kb.keywords or []) >= 1:
                return kb
    return None


def _llm_chat(messages: list[dict], config: dict) -> dict:
    """调用通用 OpenAI 兼容端点（LM Studio / DeepSeek / OpenAI…）。

    端点、Key、模型都在「软件设置 → 外部服务」或「站娘配置 → 对话模型」里配置；
    未配置/不可达时返回模拟回答（演示模式），前端会展示提示。
    """
    from .llm import chat as llm_chat
    result = llm_chat(messages)
    if result and result.get("error"):
        return result
    if result:
        return result
    # 模拟（端点不可达 / 未配置）：按问题给示例回复，token 按字符估算
    last = messages[-1]["content"] if messages else ""
    content = (
        "（演示模式）" + ("这个问题我大概懂了：参数零基础的同学直接选「标准」强度就好，"
        "层高 0.2mm、填充 20%，质量均衡。" if "参数" in last or "档" in last else
        "我是薇尔莉特～有什么和打印、模型、材料、取件相关的问题都可以问我。"
        "（当前对话端点不可用，可在「软件设置 → 外部服务」配置 OpenAI 兼容端点与模型）")
    )
    return {"content": content, "input_tokens": max(50, len(last) // 2),
            "output_tokens": max(60, len(content) // 2), "model": "demo"}


def vector_search(db: Session, question: str) -> list[dict]:
    """教材/手册向量检索（本地 embedding + TF-IDF 混合；零外部 API）。

    先过"领域闸门"：与 3D 打印/本平台无关的闲聊（今天天气、讲个笑话）不查教材，
    直接交给对话模型，避免"问天气却回一段打印 FAQ"。
    """
    try:
        from .kb_vector import is_on_topic, search
        if not is_on_topic(question):
            return []
        return search(db, question, top_k=3)
    except Exception:
        return []


STEER_BACK = (
    "我是 Violet Print 的站娘，只负责校园 3D 打印这一摊事儿，别的话题我就不展开啦。\n"
    "回到打印上：你想打什么件？我可以帮你看材料（PLA / PETG / ABS / TPU）、"
    "强度档怎么选、模型要满足什么条件，或者取件时间——挑一个问我。"
)


def ask(db: Session, user: User | None, question: str, step: str, config: dict) -> dict:
    # 1) 输入过滤（双向检测之一）
    fw = _hit_filter(question, filter_words(config))
    if fw:
        return {
            "answer": "检测到输入包含敏感内容（已拦截）。本平台仅用于校园 3D 打印服务，请围绕打印主题提问～",
            "blocked": True, "animation_key": "warn", "usage": None,
        }

    # 1.5) 领域闸门：与 3D 打印/本平台无关的闲聊 → 固定话术拉回主题，不占用本地模型
    from .kb_vector import is_on_topic
    if not is_on_topic(question):
        return {"answer": STEER_BACK, "blocked": False, "animation_key": "normal",
                "off_topic": True, "usage": None}

    # 2) 平台专属问题（强关键词命中）：不需模型，不计费
    kb = kb_search(db, question, step, strong=True)
    if kb:
        return {"answer": kb.answer, "blocked": False, "animation_key": kb.animation_key or "happy",
                "kb_hit": True, "usage": None}

    # 2.5) 向量知识库（教材/手册切块 + TF-IDF 余弦）→ 命中即作答，带出处，不花 token
    vec_hits = vector_search(db, question)
    if vec_hits:
        top = vec_hits[0]
        body = top["content"].strip()
        if len(body) > 700:
            body = body[:700].rstrip() + "…"
        others = "；".join(h["heading"] for h in vec_hits[1:3] if h["heading"] != top["heading"])
        answer = f"（来自教材 · {top['heading']}）\n{body}"
        if others:
            answer += f"\n\n相关章节还可以看：{others}"
        return {"answer": answer, "blocked": False, "animation_key": "magic",
                "kb_hit": True, "vector_hit": True,
                "sources": [{"heading": h["heading"], "score": h["score"], "source": h["source"]} for h in vec_hits],
                "usage": None}

    # 2.9) 教材没命中时，再退回弱关键词条目兜底
    weak = kb_search(db, question, step, strong=False)
    if weak:
        return {"answer": weak.answer, "blocked": False, "animation_key": weak.animation_key or "happy",
                "kb_hit": True, "usage": None}

    # 3) 大模型回答 + 输出监督
    statement = config.get("compliance", {}).get("statement", "")
    system = (config.get("qa", {}).get("system_prompt", "") or "").format(step=step or "未指定", statement=statement)
    messages = [{"role": "system", "content": system + "\n" + SUPERVISION_PROMPT}, {"role": "user", "content": question}]
    result = _llm_chat(messages, config)
    if result.get("error") == "queue_timeout":
        q = result.get("queue") or {}
        return {"answer": f"现在问的人有点多（本地模型正在处理别的提问，队列 {q.get('waiting', 0)} 个），"
                          f"稍等十几秒再问我一次；急着要知道的话，可以先翻「使用手册」。",
                "blocked": False, "animation_key": "normal", "usage": None, "queued": True}

    # 输出过滤：命中过滤词 → 将警示注入对话历史并重试一次
    out_fw = _hit_filter(result["content"], filter_words(config))
    if out_fw:
        messages.append({"role": "assistant", "content": result["content"]})
        messages.append({"role": "system",
                         "content": f"【监督拦截】上一条回复包含违禁内容（{out_fw}），已拦截。请重新输出：提醒用户本平台仅用于校园打印服务，并引导回主题。"})
        result = _llm_chat(messages, config)
    if result.get("error") == "queue_timeout":
        q = result.get("queue") or {}
        return {"answer": f"现在问的人有点多（本地模型正在处理别的提问，队列 {q.get('waiting', 0)} 个），"
                          f"稍等十几秒再问我一次；急着要知道的话，可以先翻「使用手册」。",
                "blocked": False, "animation_key": "normal", "usage": None, "queued": True}

    # 4) 用量计费（决策清单 §5：按 token，不按次）
    fee = config.get("fee", {}).get("api", {})
    in_price = fee.get("deepseek_input_per_mtok", settings.deepseek_input_price_per_mtok)
    out_price = fee.get("deepseek_output_per_mtok", settings.deepseek_output_price_per_mtok)
    return {
        "answer": result["content"], "blocked": False, "animation_key": "think",
        "model": result.get("model"),
        "usage": {
            "service": "deepseek", "input_tokens": result["input_tokens"], "output_tokens": result["output_tokens"],
            "amount": round(result["input_tokens"] / 1e6 * in_price + result["output_tokens"] / 1e6 * out_price, 4),
        },
    }
