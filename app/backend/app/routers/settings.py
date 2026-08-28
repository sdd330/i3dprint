# E3DP backend — 软件设置路由（环境变量/跨活动全局设置图形化配置，P5）
# 改动即时生效（内存覆盖 + 持久化 DB）；restart_required 项界面提示重启

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.dynamic_settings import set_override
from ..core.secrets_util import decrypt_secret, encrypt_secret, mask_secret
from ..core.security import require_permission
from ..models import AppSetting, User

router = APIRouter(prefix="/admin/settings")

DbDep = Annotated[Session, Depends(get_db)]
AdminDep = Annotated[User, Depends(require_permission("config:manage"))]


@router.get("")
def list_settings(db: DbDep, user: AdminDep):
    rows = db.query(AppSetting).order_by(AppSetting.category, AppSetting.key).all()
    groups: dict[str, list] = {}
    for r in rows:
        if r.value_type == "secret":
            # 不回显明文：只给掩码 + 是否已设置（留空 = 保持原值）
            plain = decrypt_secret(r.value)
            value_out = mask_secret(plain) if plain else ""
            secret_set = bool(plain)
        else:
            value_out, secret_set = r.value, True
        groups.setdefault(r.category, []).append({
            "key": r.key, "value": value_out, "secret_set": secret_set,
            "label": r.label, "hint": r.hint,
            "value_type": r.value_type, "restart_required": r.restart_required,
        })
    return {"groups": groups}


class SettingsIn(BaseModel):
    settings: dict[str, str]


@router.put("")
def update_settings(body: SettingsIn, db: DbDep, user: AdminDep):
    allowed = {r.key: r for r in db.query(AppSetting).all()}
    unknown = [k for k in body.settings if k not in allowed]
    if unknown:
        raise HTTPException(status_code=400, detail=f"未知设置项：{unknown}")
    for key, value in body.settings.items():
        row = allowed[key]
        if row.value_type == "secret":
            if value.strip() == "":
                continue  # 留空 = 保持原值
            encrypted = encrypt_secret(value)
            row.value = encrypted
            set_override(key, value)  # 明文入内存供服务层使用
        else:
            row.value = value
            set_override(key, value)  # 即时生效
    db.commit()
    return {"ok": True, "restart_required": [k for k, r in allowed.items() if r.restart_required and k in body.settings]}
