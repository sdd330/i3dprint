# E3DP backend — 活动（场次）管理服务
# 2026-10：新增「当前活动」指针（AppSetting.current_campaign_id）
#   之前所有地方都硬编码 `order_by(Campaign.id.desc()).first()`，只能"最新的一场"生效，
#   没法在管理界面切换场次；现在统一走 get_current_campaign(db)。

from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import AppSetting, Campaign

CURRENT_KEY = "current_campaign_id"


def list_campaigns(db: Session) -> list[Campaign]:
    return db.query(Campaign).order_by(Campaign.id.desc()).all()


def get_current_campaign(db: Session) -> Campaign | None:
    """当前生效的活动：优先取指针，其次最近一场；指针失效时自动纠正。"""
    row = db.get(AppSetting, CURRENT_KEY)
    if row and str(row.value or "").strip():
        try:
            camp = db.get(Campaign, int(row.value))
        except (TypeError, ValueError):
            camp = None
        if camp:
            return camp
    camp = db.query(Campaign).order_by(Campaign.id.desc()).first()
    if camp:
        _write_pointer(db, camp.id)
    return camp


def _write_pointer(db: Session, campaign_id: int) -> None:
    row = db.get(AppSetting, CURRENT_KEY)
    if row:
        row.value = str(campaign_id)
    else:
        db.add(AppSetting(key=CURRENT_KEY, value=str(campaign_id), category="misc",
                          label="当前活动 ID", hint="管理界面切换场次时更新；无需手动改",
                          value_type="str", restart_required=False))
    db.commit()


def set_current_campaign(db: Session, campaign_id: int) -> Campaign:
    camp = db.get(Campaign, campaign_id)
    if not camp:
        raise ValueError("活动不存在")
    _write_pointer(db, campaign_id)
    return camp
