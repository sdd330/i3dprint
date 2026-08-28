# E3DP backend — 公开元数据（活动信息/材料/档位/合规/联系人），无需登录

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models import Campaign
from ..services.config_service import get_activity_config, get_sources

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
        "presets": cfg.get("presets", []),
        "val1": cfg.get("val1", {}),
        "compliance": cfg.get("compliance", {}),
        "fee": cfg.get("fee", {}),
        "printers": _printers_out(),
    }


def _printers_out():
    from ..services.print_service import PRINTERS
    return PRINTERS
