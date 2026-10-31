# Violet Print backend — 用户管理（负责人侧）：列表 / 新建 / 改资料与角色 / 启停 / 重置密码
# 权限：user:manage（内置 admin 角色默认拥有）
# 安全约束：
#   · 不能停用/降级"最后一个可管理用户"，也不能停用自己（避免把自己锁在门外）
#   · 角色必须是已存在的角色；用户名唯一且非空
#   · 所有写操作写审计（谁改了谁、改了什么）

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import client_ip, hash_password, require_permission, write_audit
from ..models import Order, Role, User

router = APIRouter(prefix="/admin/users", tags=["users"])

DbDep = Annotated[Session, Depends(get_db)]
UserAdminDep = Annotated[User, Depends(require_permission("user:manage"))]


def _out(db: Session, u: User) -> dict:
    return {
        "id": u.id, "username": u.username, "name": u.name, "grade": u.grade, "contact": u.contact,
        "role_id": u.role_id, "role_code": u.role.code if u.role else "", "role_name": u.role.name if u.role else "",
        "is_active": u.is_active, "created_at": u.created_at,
        "orders": db.query(Order).filter_by(user_id=u.id).count(),
    }


PROTECTED_USERNAME = "root"   # 最底层管理员：不可删除 / 停用 / 降级


def _is_protected(u: User) -> bool:
    return u.username == PROTECTED_USERNAME or (u.role and u.role.code == "root")


def _active_admins(db: Session) -> list[User]:
    return (db.query(User).join(Role, User.role_id == Role.id)
            .filter(User.is_active.is_(True), Role.permissions.contains("user:manage")).all())


@router.get("")
def list_users(db: DbDep, user: UserAdminDep, q: str = "", role_id: int | None = None,
               active: bool | None = None):
    """用户列表（支持关键字搜索用户名/姓名/学号、按角色、按启用状态筛选）。"""
    query = db.query(User)
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter((User.username.like(like)) | (User.name.like(like)) | (User.grade.like(like)))
    if role_id:
        query = query.filter(User.role_id == role_id)
    if active is not None:
        query = query.filter(User.is_active.is_(active))
    rows = query.order_by(User.id).all()
    return {"users": [_out(db, u) for u in rows],
            "roles": [{"id": r.id, "code": r.code, "name": r.name} for r in db.query(Role).all()]}


class UserCreateIn(BaseModel):
    username: str
    name: str = ""
    password: str
    role_id: int
    grade: str = ""
    contact: str = ""


@router.post("")
def create_user(body: UserCreateIn, db: DbDep, user: UserAdminDep, request: Request):
    username = (body.username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="用户名 / 学号不能为空")
    if db.query(User).filter_by(username=username).first():
        raise HTTPException(status_code=409, detail="该用户名 / 学号已存在")
    if len(body.password or "") < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")
    role = db.get(Role, body.role_id)
    if not role:
        raise HTTPException(status_code=400, detail="角色不存在")
    u = User(username=username, name=(body.name or username).strip(), grade=body.grade.strip(),
             contact=body.contact.strip(), hashed_password=hash_password(body.password), role_id=role.id)
    db.add(u)
    db.commit()
    db.refresh(u)
    write_audit(db, user, "user.create", target=username, detail=f"role={role.code}", ip=client_ip(request))
    return {"ok": True, "user": _out(db, u)}


class UserUpdateIn(BaseModel):
    name: str | None = None
    grade: str | None = None
    contact: str | None = None
    role_id: int | None = None
    is_active: bool | None = None


@router.put("/{user_id}")
def update_user(user_id: int, body: UserUpdateIn, db: DbDep, user: UserAdminDep, request: Request):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if _is_protected(target):
        raise HTTPException(status_code=403, detail="root 为受保护的超级管理员，不能在用户管理里修改（口令请用右上角「修改密码」）")
    changes = []

    if body.role_id is not None and body.role_id != target.role_id:
        role = db.get(Role, body.role_id)
        if not role:
            raise HTTPException(status_code=400, detail="角色不存在")
        # 防锁死：把最后一个 user:manage 用户降级是不允许的
        if "user:manage" in (target.role.permissions or []) and "user:manage" not in (role.permissions or []):
            if len(_active_admins(db)) <= 1:
                raise HTTPException(status_code=409, detail="这是最后一个拥有用户管理权限的账号，不能降级")
        target.role_id = role.id
        changes.append(f"角色→{role.name}")

    if body.is_active is not None and body.is_active != target.is_active:
        if not body.is_active:
            if target.id == user.id:
                raise HTTPException(status_code=409, detail="不能停用自己的账号")
            if "user:manage" in (target.role.permissions or []) and len(_active_admins(db)) <= 1:
                raise HTTPException(status_code=409, detail="这是最后一个拥有用户管理权限的账号，不能停用")
        target.is_active = body.is_active
        changes.append("启用" if body.is_active else "停用")

    for field, label in (("name", "姓名"), ("grade", "年级"), ("contact", "联系方式")):
        val = getattr(body, field)
        if val is not None and val.strip() != (getattr(target, field) or ""):
            setattr(target, field, val.strip())
            changes.append(label)

    db.commit()
    db.refresh(target)   # 角色改了要刷新关系，否则返回体里还是旧角色
    write_audit(db, user, "user.update", target=target.username, detail="、".join(changes), ip=client_ip(request))
    return {"ok": True, "user": _out(db, target)}


class PasswordIn(BaseModel):
    password: str


@router.post("/{user_id}/password")
def reset_password(user_id: int, body: PasswordIn, db: DbDep, user: UserAdminDep, request: Request):
    """负责人重置某个用户的密码（学生忘记密码时用）。"""
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if _is_protected(target) and not _is_protected(user):
        raise HTTPException(status_code=403, detail="只有 root 本人可以重置 root 的口令")
    if len(body.password or "") < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")
    target.hashed_password = hash_password(body.password)
    db.commit()
    write_audit(db, user, "user.reset_password", target=target.username, ip=client_ip(request))
    return {"ok": True}


@router.delete("/{user_id}")
def delete_user(user_id: int, db: DbDep, user: UserAdminDep, request: Request, force: bool = False):
    """删除用户：默认只允许删除没有需求记录的用户（有记录请改「停用」以保留追溯）。"""
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if _is_protected(target):
        raise HTTPException(status_code=403, detail="root 为受保护的超级管理员，不能删除")
    if target.id == user.id:
        raise HTTPException(status_code=409, detail="不能删除自己的账号")
    if "user:manage" in (target.role.permissions or []) and len(_active_admins(db)) <= 1:
        raise HTTPException(status_code=409, detail="这是最后一个拥有用户管理权限的账号，不能删除")
    orders = db.query(Order).filter_by(user_id=target.id).count()
    if orders and not force:
        raise HTTPException(status_code=409, detail=f"该用户有 {orders} 条需求记录，请改为停用")
    name = target.username
    db.delete(target)
    db.commit()
    write_audit(db, user, "user.delete", target=name, detail=f"orders={orders}", ip=client_ip(request))
    return {"ok": True}
