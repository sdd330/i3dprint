# E3DP backend — 安全：密码哈希 / JWT / RBAC 依赖 / 审计（决策清单 §9）

import time
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import get_db
from ..models import AuditLog, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

# 登录失败限流（内存计数，单进程 demo 够用；多进程部署时换 Redis）
_login_failures: dict[str, list[float]] = {}


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(user_id: int, username: str, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": int(time.time()) + settings.jwt_expire_minutes * 60,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _check_login_rate(ip: str):
    now = time.time()
    window = 60
    _login_failures[ip] = [t for t in _login_failures.get(ip, []) if now - t < window]
    if len(_login_failures[ip]) >= settings.login_rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="登录失败次数过多，请 1 分钟后再试")


def record_login_failure(ip: str):
    _login_failures.setdefault(ip, []).append(time.time())


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if creds is None:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        payload = jwt.decode(creds.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已停用")
    return user


def require_permission(permission: str):
    """RBAC 依赖工厂：校验当前用户角色是否拥有权限点（决策清单 §9 角色-权限解耦）"""

    def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if permission not in (user.role.permissions or []):
            raise HTTPException(status_code=403, detail=f"无权限：{permission}")
        return user

    return checker


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role.code != "admin":
        raise HTTPException(status_code=403, detail="仅负责人可操作")
    return user


def write_audit(db: Session, user: User | None, action: str, target: str = "", detail: str = "", ip: str = ""):
    """操作日志（§13.4）"""
    db.add(AuditLog(
        user_id=user.id if user else None,
        username=user.username if user else "",
        action=action,
        target=target,
        detail=detail[:500],
        ip=ip,
    ))
    db.commit()


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else request.client.host if request.client else ""
