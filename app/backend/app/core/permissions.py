"""权限点定义：RBAC，角色=权限点集合，与模块解耦（实现决策清单 §9）。"""
from __future__ import annotations

# 权限点（模块:操作），新增模块时在此扩展，不写死在代码逻辑里
PERMISSIONS: list[str] = [
    # 订单
    "order:create", "order:read:own", "order:read:all", "order:write:own", "order:write:all",
    # 三级审核
    "val1:review", "val2:review", "val3:review",
    # 打印与设备
    "print:manage", "printer:read",
    # 活动与账单
    "campaign:read", "campaign:manage", "bill:view",
    # 配置中心与权限
    "config:manage", "role:manage", "audit:view",
    # 独立模块
    "ai:use", "qa:ask", "qa:ticket", "qa:manage",
]

STUDENT_PERMISSIONS: list[str] = [
    "order:create", "order:read:own", "order:write:own",
    "printer:read", "campaign:read",
    "ai:use", "qa:ask", "qa:ticket",
]

ADMIN_PERMISSIONS: list[str] = list(PERMISSIONS)

DEFAULT_ROLES: list[dict] = [
    {"id": 1, "name": "admin", "description": "负责人：审核/打印/活动/账单/配置/权限全权", "permissions": ADMIN_PERMISSIONS},
    {"id": 2, "name": "student", "description": "学生参与者：管理自己的需求、AI建模、站娘问答", "permissions": STUDENT_PERMISSIONS},
]
