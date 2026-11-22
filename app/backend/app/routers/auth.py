# E3DP backend — 认证路由（决策清单 §9：学号+密码登录、bcrypt、JWT）

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import (
    check_login_rate,
    client_ip,
    create_token,
    ensure_student_id,
    get_current_user,
    hash_password,
    is_staff,
    record_login_failure,
    verify_password,
    write_audit,
)
from ..models import Role, User
from ..services.campaign_service import verify_access_password

router = APIRouter()


class RegisterIn(BaseModel):
    username: str = Field(min_length=1, max_length=64, description="8 位学号，如 20280101")
    name: str = Field(min_length=1, max_length=64)
    grade: str = ""
    contact: str = ""
    password: str = Field(min_length=6, max_length=64)
    campaign_password: str = Field(default="", description="活动口令（负责人线下发放）")


class LoginIn(BaseModel):
    username: str
    password: str
    campaign_password: str = Field(default="", description="活动口令（负责人线下发放）")


@router.post("/register")
def register(body: RegisterIn, request: Request, db: Annotated[Session, Depends(get_db)]):
    username = ensure_student_id(body.username)
    if db.query(User).filter_by(username=username).first():
        raise HTTPException(status_code=409, detail="该学号已登记")
    verify_access_password(db, body.campaign_password, staff=False, ip=client_ip(request))
    stu_role = db.query(Role).filter_by(code="student").first()
    user = User(
        username=username, name=body.name, grade=body.grade, contact=body.contact,
        hashed_password=hash_password(body.password), role_id=stu_role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    write_audit(db, user, "auth.register", target=user.username, ip=client_ip(request))
    return {"token": create_token(user.id, user.username, user.role.code), "user": _user_out(user)}


@router.post("/login")
def login(body: LoginIn, request: Request, db: Annotated[Session, Depends(get_db)]):
    ip = client_ip(request)
    check_login_rate(ip)
    user = db.query(User).filter_by(username=body.username).first()
    if not user or not verify_password(body.password, user.hashed_password):
        record_login_failure(ip)
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    # 账号密码通过后，非负责人侧还要过活动口令这一关
    verify_access_password(db, body.campaign_password, staff=is_staff(user), ip=ip)
    write_audit(db, user, "auth.login", target=user.username, ip=ip)
    return {"token": create_token(user.id, user.username, user.role.code), "user": _user_out(user)}


class PasswordChangeIn(BaseModel):
    old_password: str
    new_password: str


@router.post("/password")
def change_password(body: PasswordChangeIn, request: Request,
                    user: Annotated[User, Depends(get_current_user)],
                    db: Annotated[Session, Depends(get_db)]):
    """修改自己的密码（所有人可用）。"""
    if not verify_password(body.old_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="原密码不正确")
    if len(body.new_password or "") < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 位")
    user.hashed_password = hash_password(body.new_password)
    db.commit()
    write_audit(db, user, "auth.password_change", target=user.username, ip=client_ip(request))
    return {"ok": True}


@router.get("/me")
def me(user: Annotated[User, Depends(get_current_user)]):
    return {"user": _user_out(user)}


def _user_out(u: User) -> dict:
    return {
        "id": u.id, "username": u.username, "name": u.name, "grade": u.grade,
        "contact": u.contact, "role": u.role.code, "role_name": u.role.name,
        "permissions": u.role.permissions,
    }
