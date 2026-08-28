# E3DP backend — 两级状态机（设计文档 §12）
# 第一级：活动状态（待开放/开放中/收尾中/已归档）
# 第二级：订单状态（16 态，在所属活动内流转；摆放/尺寸调整为 Modeling 子阶段）

from ..models.entities import CAMPAIGN_STATUS, ORDER_STATUS


class StateError(Exception):
    pass


# 订单状态迁移表
TRANSITIONS = {
    "draft": ["modeling", "terminated"],
    "modeling": ["val1_pending", "draft", "terminated"],
    "val1_pending": ["slicing", "val1_failed", "val1_appeal", "terminated"],
    "val1_failed": ["modeling", "val1_pending", "terminated"],  # 修改模型→新版本→重新提交
    "val1_appeal": ["slicing", "val1_failed", "terminated"],  # 人工审核：同意/要求修改/判定不通过
    "slicing": ["val2_pending", "val2_failed", "modeling", "terminated"],  # 切片失败→改参/改模型
    "val2_pending": ["queued", "val2_failed", "terminated"],
    "val2_failed": ["slicing", "modeling", "terminated"],  # 参数/切片→重切；模型→新版本Val1；内容不合规→终止
    "queued": ["printing", "terminated"],
    "printing": ["val3_pending", "queued", "terminated"],  # 打印异常→重新排队（§16.4）
    "val3_pending": ["settlement", "val3_failed", "rework"],
    "val3_failed": ["rework", "terminated"],
    "rework": ["slicing", "modeling", "queued", "terminated"],  # 参数→重切；模型→新版本Val1；设备→重打
    "settlement": ["completed", "terminated"],
    "completed": [],
    "terminated": [],
}

CAMPAIGN_TRANSITIONS = {
    "待开放": ["开放中"],
    "开放中": ["收尾中"],
    "收尾中": ["已归档"],
    "已归档": [],
}

TERMINAL = {"completed", "terminated"}


def transition(order, to, note: str = "", at: str | None = None):
    """迁移订单状态；成功返回 timeline 条目，失败抛 StateError"""
    if order.status == to:
        return
    if to not in TRANSITIONS.get(order.status, []):
        raise StateError(f"状态迁移不合法：{ORDER_STATUS.get(order.status, order.status)} → {ORDER_STATUS.get(to, to)}")
    if order.status in TERMINAL:
        raise StateError("终态订单不可再迁移")
    from datetime import datetime
    order.status = to
    entry = {"t": at or datetime.utcnow().isoformat(timespec="seconds"), "status": to, "note": note}
    order.timeline = list(order.timeline or []) + [entry]
    order.updated_at = entry["t"]
    return entry


def can_transition(order, to) -> bool:
    return to in TRANSITIONS.get(order.status, [])


def transition_campaign(campaign, to):
    """迁移活动状态"""
    if campaign.status == to:
        return
    if to not in CAMPAIGN_TRANSITIONS.get(campaign.status, []):
        raise StateError(f"活动状态迁移不合法：{campaign.status} → {to}")
    campaign.status = to


def assert_campaign_open(campaign):
    """活动级联动约束（§12.3）：仅开放中可创建需求"""
    if campaign.status != "开放中":
        raise StateError(f"当前活动状态为「{campaign.status}」，仅开放中可创建打印需求")
