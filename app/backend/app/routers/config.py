# E3DP backend — 配置中心与角色管理路由（决策清单 §9 RBAC / §14 配置中心）

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import require_permission
from ..models import AuditLog, Campaign, ConfigAudit, ConfigTemplate, Role, User
from ..models.permissions import PERMISSIONS
from ..services.config_service import CATEGORIES, get_activity_config, get_default_template, set_category

router = APIRouter(prefix="/admin")

DbDep = Annotated[Session, Depends(get_db)]
AdminDep = Annotated[User, Depends(require_permission("config:manage"))]


# ---------- 配置中心（§14） ----------

@router.get("/config/template")
def get_template(db: DbDep, user: AdminDep):
    tpl = get_default_template(db)
    return {"template": {"id": tpl.id, "name": tpl.name, "data": tpl.data}}


class CategoryIn(BaseModel):
    # 分类数据可以是对象（如 fee）也可以是数组（如 presets / strength_tiers）——
    # 之前限定 dict 导致列表型分类保存直接 422，配置中心里"参数档改了不生效"。
    data: Any


@router.put("/config/template/{category}")
def update_template_category(category: str, body: CategoryIn, db: DbDep, user: AdminDep):
    if category not in CATEGORIES:
        raise HTTPException(status_code=400, detail=f"未知参数分类：{category}")
    set_category(db, "template", None, category, body.data, operator=user.username)
    return {"ok": True}


class SyncTemplateIn(BaseModel):
    campaign_id: int | None = None


@router.post("/config/template/from-campaign")
def sync_template(body: SyncTemplateIn | None = None, db: DbDep = None, user: AdminDep = None):
    """把指定活动（默认当前活动）的参数同步到默认模板：以后新建活动继承这套基线。"""
    from ..services.campaign_service import get_current_campaign
    from ..services.config_service import sync_template_from_campaign
    cid = (body.campaign_id if body else None)
    campaign = db.get(Campaign, cid) if cid else get_current_campaign(db)
    if not campaign:
        raise HTTPException(status_code=404, detail="活动不存在")
    result = sync_template_from_campaign(db, campaign, operator=user.username)
    return {"ok": True, **result}


@router.get("/config/campaign/{campaign_id}")
def get_campaign_config(campaign_id: int, db: DbDep, user: AdminDep):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="活动不存在")
    cfg = get_activity_config(db, campaign)
    return {"config": cfg, "sources": cfg.get("_sources", {})}


@router.put("/config/campaign/{campaign_id}/{category}")
def update_campaign_category(campaign_id: int, category: str, body: CategoryIn, db: DbDep, user: AdminDep):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="活动不存在")
    if category not in CATEGORIES:
        raise HTTPException(status_code=400, detail=f"未知参数分类：{category}")
    set_category(db, "campaign", campaign.id, category, body.data, operator=user.username, campaign=campaign)
    return {"ok": True}


@router.get("/config/audits")
def list_audits(db: DbDep, user: AdminDep):
    audits = db.query(ConfigAudit).order_by(ConfigAudit.id.desc()).limit(100).all()
    return {"audits": [{"id": a.id, "scope": a.scope, "category": a.category, "path": a.path,
                        "operator": a.operator, "at": a.at, "old": a.old_value[:120], "new": a.new_value[:120]}
                       for a in audits]}


# ---------- 角色与权限（§9：RBAC 可配置、解耦） ----------

@router.get("/permissions")
def list_permissions(db: DbDep, user: AdminDep):
    return {"permissions": [{"code": k, "name": v} for k, v in PERMISSIONS.items()]}


@router.get("/roles")
def list_roles(db: DbDep, user: AdminDep):
    roles = db.query(Role).all()
    return {"roles": [{"id": r.id, "code": r.code, "name": r.name, "permissions": r.permissions, "builtin": r.builtin}
                      for r in roles]}


class RoleIn(BaseModel):
    name: str
    permissions: list[str]


@router.put("/roles/{role_id}")
def update_role(role_id: int, body: RoleIn, db: DbDep, user: AdminDep):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.code == "root":
        raise HTTPException(status_code=403, detail="root 角色为受保护角色，不可修改（始终拥有全部权限）")
    unknown = [p for p in body.permissions if p not in PERMISSIONS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"未知权限点：{unknown}")
    role.name = body.name
    role.permissions = body.permissions
    db.commit()
    return {"ok": True}


@router.post("/roles")
def create_role(body: RoleIn, db: DbDep, user: AdminDep):
    code = f"custom{len(db.query(Role).all()) + 1}"
    role = Role(code=code, name=body.name, permissions=body.permissions, builtin=False)
    db.add(role)
    db.commit()
    db.refresh(role)
    return {"ok": True, "role": {"id": role.id, "code": role.code, "name": role.name, "permissions": role.permissions}}


@router.get("/audit-logs")
def list_audit_logs(db: DbDep, user: Annotated[User, Depends(require_permission("config:manage"))]):
    logs = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(100).all()
    return {"logs": [{"id": l.id, "username": l.username, "action": l.action, "target": l.target,
                      "detail": l.detail, "ip": l.ip, "at": l.at} for l in logs]}
