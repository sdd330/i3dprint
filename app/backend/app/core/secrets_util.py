# E3DP backend — secret 加密工具（P5 安全改造：API Key 等加密存储 + 掩码回显）
# Fernet 对称加密；密钥派生自 JWT_SECRET（更改 JWT_SECRET 会使已存 secret 失效——界面已提示）

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from .config import settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.jwt_secret.encode()).digest())
        _fernet = Fernet(key)
    return _fernet


def encrypt_secret(plain: str) -> str:
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_secret(token: str) -> str | None:
    """解密失败（如 JWT_SECRET 已变更）返回 None"""
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None


def mask_secret(value: str) -> str:
    """掩码：保留前 4 后 4，中段用 ****（短值整体掩码）"""
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"
