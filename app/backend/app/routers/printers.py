# E3DP backend — 打印机清单（设备来自配置中心 `print.printers`，忙闲状态取自运行时）

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import require_permission
from ..models import Campaign
from ..services.campaign_service import get_current_campaign
from ..models.entities import User
from ..services.config_service import get_activity_config
from ..services.print_service import printer_snapshot

router = APIRouter(prefix="/api", tags=["printers"])


@router.get("/printers")
def list_printers(db: Annotated[Session, Depends(get_db)],
                  user: Annotated[User, Depends(require_permission("printer:read"))]):
    """设备清单（配置中心可增删/启停）+ 运行时忙闲状态 + 打印范围。"""
    campaign = get_current_campaign(db)
    cfg = get_activity_config(db, campaign) if campaign else {}
    return {"printers": printer_snapshot(cfg)}
