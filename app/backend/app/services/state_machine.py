# E3DP backend — 两级状态机（设计文档 §12）
# 第一级：活动状态（待开放/开放中/收尾中/已归档）
# 第二级：订单状态（在所属活动内流转；摆放/尺寸调整为 Modeling 子阶段）
#
# 2026-10 调整（在线切片 + Val2 切片核验暂缓）：
#   val1_pending ─ 无潜在问题 ─→ print_config（打印需求配置）
#                └─ 标记潜在问题 ─→ val1_review（人工审核，**不退回用户**）
#   print_config ─ 提交打印需求 ─→ queued（打印清单，负责人据此执行打印）
#   旧状态 slicing / val2_pending / val2_failed / val1_appeal 保留定义以兼容历史数据，
#   新链路不再产生（启动时 seed() 会把历史数据迁移到新状态）。

from ..models.entities import CAMPAIGN_STATUS, ORDER_STATUS


class StateError(Exception):
    pass


# 订单状态迁移表
TRANSITIONS = {
    "draft": ["modeling", "terminated"],
    "modeling": ["val1_pending", "draft", "terminated"],
    # Val1 自动审核：无潜在问题直接进打印需求；有潜在问题只做「标记 + 转人工」，无自动退回
    "val1_pending": ["print_config", "val1_review", "terminated"],
    # 人工复核：放行 / 要求修改模型（人工退回）/ 终止
    "val1_review": ["print_config", "val1_failed", "terminated"],
    "val1_failed": ["modeling", "terminated"],  # 用户改模型 → 重走摆放与 Val1
    # 打印需求配置（材料 / 强度 / 进阶参数）
    "print_config": ["queued", "modeling", "terminated"],
    "queued": ["printing", "terminated"],  # 打印清单，等待执行打印
    "printing": ["val3_pending", "queued", "terminated"],  # 打印异常→重新排队（§16.4）
    "val3_pending": ["settlement", "val3_failed", "rework", "terminated"],  # §10.4 设备能力上限 → 终止
    "val3_failed": ["rework", "terminated"],
    "rework": ["print_config", "modeling", "queued", "terminated"],  # 参数→改打印需求；模型→改模型；设备→重打
    "settlement": ["completed", "terminated"],
    "completed": [],
    "terminated": [],
    # —— 已暂缓（在线切片 + Val2），仅为历史数据兼容保留 ——
    "val1_appeal": ["print_config", "val1_failed", "terminated"],
    "slicing": ["print_config", "modeling", "terminated"],
    "val2_pending": ["queued", "print_config", "terminated"],
    "val2_failed": ["print_config", "modeling", "terminated"],
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
