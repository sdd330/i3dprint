# E3DP backend — 软件全局设置（环境变量图形化配置，跨活动不变）
# 架构：env 提供默认值；AppSetting 表持久化用户覆盖；运行时动态读取（改完即时生效）
# 重启类设置（host/port/jwt_secret）标 restart_required，界面提示

from __future__ import annotations

from typing import Any

# 内存覆盖层：PUT 设置后即时生效（无需重启）；启动时从 DB 加载
_overrides: dict[str, str] = {}


def set_override(key: str, value: Any):
    _overrides[key] = str(value)


def clear_overrides():
    _overrides.clear()


def get_setting(key: str, default: Any = None) -> Any:
    """动态读取：覆盖层 > 默认值（默认值来自 env settings）"""
    if key in _overrides:
        v = _overrides[key]
        # 按默认值类型还原
        if isinstance(default, bool):
            return v.lower() in ("1", "true", "yes", "on")
        if isinstance(default, int):
            try:
                return int(float(v))
            except ValueError:
                return default
        if isinstance(default, float):
            try:
                return float(v)
            except ValueError:
                return default
        return v
    return default


def load_from_db(db):
    """启动时调用：从 AppSetting 表加载持久化覆盖；secret 类型解密为明文供服务层使用"""
    from ..models import AppSetting
    from .secrets_util import decrypt_secret
    clear_overrides()
    for row in db.query(AppSetting).all():
        if row.value_type == "secret":
            plain = decrypt_secret(row.value)
            if plain is not None:
                _overrides[row.key] = plain
        else:
            _overrides[row.key] = row.value
