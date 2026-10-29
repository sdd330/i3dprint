# E3DP backend — 公开元数据（活动信息/材料/强度档/合规/联系人），无需登录

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models import Campaign
from ..services.config_service import get_activity_config, get_sources
from ..services.print_requirement import strength_tiers

router = APIRouter()


@router.get("/bootstrap")
def bootstrap(db: Annotated[Session, Depends(get_db)]):
    campaign = db.query(Campaign).order_by(Campaign.id.desc()).first()
    cfg = get_activity_config(db, campaign) if campaign else {}
    return {
        "campaign": {
            "id": campaign.id, "name": campaign.name, "status": campaign.status,
            "password": campaign.password if campaign.status != "已归档" else "****",
            "open_at": campaign.open_at, "close_at": campaign.close_at,
            "max_participants": campaign.max_participants,
            "config_sources": get_sources(campaign) if campaign else {},
        } if campaign else None,
        "materials": cfg.get("fee", {}).get("materials", []),
        "strength_tiers": strength_tiers(cfg),  # 打印需求「强度」档（配置中心可编辑）
        "presets": cfg.get("presets", []),
        "val1": cfg.get("val1", {}),
        "compliance": cfg.get("compliance", {}),
        "fee": cfg.get("fee", {}),
        "printers": _printers_out(cfg),
        # 能力开关（前端据此隐藏入口，后端逻辑保留可随时恢复）
        "flow": {
            "online_slicing": False,   # 在线切片（OrcaSlicer）已暂缓
            "val2_review": False,      # Val2 切片核验已暂缓
            "val1_sendback": False,    # Val1 不再自动退回，只标记 + 转人工
            "billing_visible": False,  # 收费/费用信息暂时隐去
            "ai_modeling": False,      # AI 建模入口暂时关闭（后端接口保留）
        },
    }


def _printers_out(cfg: dict | None = None):
    """设备清单来自活动配置（配置中心「打印/设备」可增删），忙闲状态取自运行时。"""
    from ..services.print_service import printer_snapshot
    return printer_snapshot(cfg)
