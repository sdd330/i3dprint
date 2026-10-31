# E3DP backend — 权限点定义（RBAC，决策清单 §9：角色与模块权限解耦）

# 权限点命名：<模块>:<操作>
PERMISSIONS = {
    # 学生侧
    "order:create": "创建打印需求",
    "order:read_own": "查看自己的需求",
    "order:update_own": "修改自己的需求（摆放/参数/申诉/反馈）",
    "model:upload": "上传模型",
    "ai:use": "使用 AI 建模",
    "qa:ask": "站娘问答",
    "qa:ticket": "提交问答工单",
    # 负责人侧
    "val1:review": "Val1 申诉人工审核",
    "val2:review": "Val2 人工切片审核 + 内容合规审核",
    "val3:review": "Val3 实物验收 + 责任判定",
    "print:manage": "打印队列与任务管理（开始/完成/异常重排/手动填写时间）",
    "printer:read": "查看打印机清单与忙闲状态",
    "filament:review": "自备耗材检验",
    "campaign:manage": "活动生命周期管理（开放/收尾/归档）",
    "bill:view": "活动账单查看",
    "config:manage": "配置中心管理",
    "role:manage": "角色与权限管理",
    "user:manage": "用户管理（列表 / 改角色 / 启停 / 重置密码）",
    "qa:manage": "站娘配置与工单管理",
    "order:view_all": "查看全部需求（负责人）",
}

DEFAULT_ROLES = {
    # 最底层超级管理员：拥有全部权限，角色与账号均受保护（不可编辑/删除/停用/降级）
    "root": {
        "name": "超级管理员（受保护）",
        "permissions": list(PERMISSIONS.keys()),
    },
    "student": {
        "name": "学生参与者",
        "permissions": [
            "order:create", "order:read_own", "order:update_own", "model:upload",
            "ai:use", "qa:ask", "qa:ticket",
        ],
    },
    "admin": {
        "name": "平台负责人",
        "permissions": list(PERMISSIONS.keys()),
    },
}
