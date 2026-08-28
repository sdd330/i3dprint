# E3DP backend — AI 辅助建模路由（设计文档 §14 / 决策清单 §5：Tripo AI SDK）
# 真实实现：Tripo AI SDK 生成（task 制）→ 服务端 trimesh 就地体检（与 Val1 同源）
# 首版：程序化生成演示模型 + 真实 trimesh 分析；Tripo 真实调用预留（配置 key 后启用）

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import get_db
from ..core.security import get_current_user
from ..models import Campaign, User
from ..services.config_service import get_activity_config
from ..services.cost import append_api_usage
from ..services.val1 import analyze_mesh, build_preset, run_val1

router = APIRouter()

DbDep = Annotated[Session, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]

PRESET_HINTS = [
    ("花瓶", "vase"), ("机器人", "robot"), ("支架", "stand"),
    ("笔筒", "penholder"), ("陀螺", "spinner"),
]


class GenerateIn(BaseModel):
    description: str = ""
    size_cm: float = 8


@router.post("/generate")
def ai_generate(body: GenerateIn, db: DbDep, user: UserDep):
    campaign = db.query(Campaign).order_by(Campaign.id.desc()).first()
    config = get_activity_config(db, campaign) if campaign else {}

    # 匹配生成类型（真实 Tripo：text-to-3d；demo：程序化生成）
    kind = "generic"
    for hint, k in PRESET_HINTS:
        if hint in body.description:
            kind = k
            break
    mesh = build_preset(kind)
    stats = analyze_mesh(mesh)

    # 就地打印体检（§14.2，与 Val1 同源）
    val1_cfg = config.get("val1", {})
    report = run_val1(stats, {**config, "val1": val1_cfg}, "", kind)

    # 用量计费（决策清单 §5：Tripo 按点数）
    fee = config.get("fee", {}).get("api", {})
    points = 5.0  # 模拟一次生成消耗（真实 SDK 返回实际消耗）
    unit_price = fee.get("tripo_per_point", settings.tripo_price_per_point)
    usage = append_api_usage(db, kind="ai_modeling", service="tripo", user_id=user.id,
                             points=points, unit_price=unit_price, meta={"kind": kind, "desc": body.description[:50]})

    return {
        "kind": kind,
        "name": f"AI 生成 · {'/'.join(h for h, k in PRESET_HINTS if k == kind) or '自定义模型'}",
        "stats": stats,
        "report": report,
        "usage": {"service": "tripo", "points": points, "unit_price": unit_price, "amount": usage.amount},
        "note": "生成结果未直接进入打印：请确认后下载，或自动填充到上传环节照走 Val1/Val2 全部审核（§14.1）",
    }
