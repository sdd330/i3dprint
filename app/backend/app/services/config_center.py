"""配置中心（实现决策清单 §14）：默认活动模板 + 活动参数可选继承 + 修改审计。
所有关键业务参数集中于此，不写死在代码里；活动级参数复制为副本，可按项覆盖。
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models.entities import ConfigSet

# 默认活动模板（全局基线）：新建活动时可继承，也可继承上一场活动
DEFAULT_TEMPLATE: dict = {
    "activity": {
        "max_participants": 20,
        "appeal_limit_per_campaign": 5,   # 每场申诉审核上限（§5.3）
        "appeal_limit_per_model": 2,      # 单模型申诉次数上限
        "notice": "校园3D打印活动：、费用只覆盖成本非营利；活动结束后统一收款。",
    },
    "cost": {
        "materials": [  # 材料价格表：成本价(元/g) × 材料系数 + 换料补偿
            {"id": "pla", "name": "PLA 聚乳酸", "price_per_gram": 0.10, "coeff": 1.0, "density": 1.24},
            {"id": "petg", "name": "PETG 共聚酯", "price_per_gram": 0.16, "coeff": 1.2, "density": 1.27},
            {"id": "abs", "name": "ABS 工程塑料", "price_per_gram": 0.14, "coeff": 1.15, "density": 1.04},
            {"id": "tpu", "name": "TPU 柔性材料", "price_per_gram": 0.22, "coeff": 1.3, "density": 1.21},
        ],
        "color_change_fee": 1.5,        # 换料补偿（元/次）
        "maintenance_per_job": 0.6,     # 维护费：每任务固定摊分（元）
        "maintenance_per_gram": 0.004,  # 维护费：每克摊分（元/g）
        "machine_reprint_rate": 1.0,    # 设备问题重打按正常耗材费比例（2026-10 起取消半价：一律 100%）
        "api_prices": {                 # API 单价（元）
            "deepseek_input_per_1k": 0.001,   # DeepSeek 输入 token 每 1k
            "deepseek_output_per_1k": 0.002,  # DeepSeek 输出 token 每 1k
            "tripo_per_point": 0.5,           # Tripo 点数单价
        },
    },
    "val1": {  # §5.1 阈值
        "wall_min_hard_mm": 0.8,   # 壁厚低于 → 不通过
        "wall_min_soft_mm": 1.2,   # 壁厚低于 → 警告
        "overhang_warn_pct": 30,   # 悬垂占比超过 → 警告
        "overhang_hard_pct": 55,   # 悬垂占比超过 → 不通过
        "build_volume_mm": [256, 256, 256],  # X1C 打印范围
        "checks_enabled": ["integrity", "closed", "manifold", "self_intersect", "size", "wall", "overhang", "material", "params", "sliceable"],
    },
    "params": {  # §4.2 标准档（参考 OrcaSlicer 常用配置字段）
        "presets": [
            {"id": "fast", "name": "快速档", "layer_height": 0.28, "infill": 15, "speed": 200, "supports": "auto", "note": "速度快，细节一般"},
            {"id": "standard", "name": "标准档", "layer_height": 0.2, "infill": 20, "speed": 150, "supports": "auto", "note": "质量均衡，日常推荐"},
            {"id": "fine", "name": "精细档", "layer_height": 0.12, "infill": 25, "speed": 100, "supports": "auto", "note": "细节好，耗时较长"},
        ],
        "manual_fields": ["layer_height", "infill", "speed", "supports", "temperature", "wall_count"],
    },
    "compliance": {  # §7.4 合规清单（界面可维护）
        "prohibited": ["管制刀具/武器类", "危险品/易燃易爆", "明显违规用途", "其他平台规定禁止打印的内容"],
        "declaration": "最终解释权归 FRC Team 6940 所有，任何人不得用作商业用途。",
    },
    "ops": {  # §16 配套运营
        "pickup_location": "创新中心 3D 打印室（活动期间）",
        "pickup_window": "活动结束前 2 小时至活动结束后 1 天",
        "contacts": [  # 每年级 2 名线下负责人
            {"grade": "大一", "members": [{"name": "李同学", "phone": "138****1024"}, {"name": "王同学", "phone": "139****8876"}]},
            {"grade": "大二", "members": [{"name": "张同学", "phone": "137****3345"}, {"name": "刘同学", "phone": "136****9901"}]},
            {"grade": "大三", "members": [{"name": "陈同学", "phone": "135****2210"}, {"name": "赵同学", "phone": "133****5678"}]},
            {"grade": "大四", "members": [{"name": "周同学", "phone": "132****4456"}, {"name": "吴同学", "phone": "131****7789"}]},
        ],
    },
    "qa": {  # §15 站娘（知识库/System Prompt 为独立表，此处放开关类）
        "enable_supervision": True,
        "animation_enabled": True,
    },
}


def ensure_default_template(db: Session) -> ConfigSet:
    """确保默认活动模板存在（首次启动创建）。"""
    tpl = db.query(ConfigSet).filter_by(kind="template", name="默认活动模板").first()
    if not tpl:
        tpl = ConfigSet(name="默认活动模板", kind="template", source=None, data=deepcopy(DEFAULT_TEMPLATE))
        db.add(tpl)
        db.commit()
        db.refresh(tpl)
    return tpl


def create_campaign_config(db: Session, name: str, inherit_from: ConfigSet | None) -> ConfigSet:
    """新建活动参数副本：继承默认模板或指定活动/模板（可选继承）。"""
    base = inherit_from or ensure_default_template(db)
    cfg = ConfigSet(
        name=f"{name} 参数",
        kind="campaign",
        source={"kind": base.kind, "ref": base.id, "label": base.name},
        data=deepcopy(base.data),
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


def get_config(db: Session, campaign) -> dict:
    """取活动的生效参数（活动副本不存在则回退默认模板）。"""
    if campaign and campaign.config_id:
        cfg = db.get(ConfigSet, campaign.config_id)
        if cfg:
            return cfg.data
    return ensure_default_template(db).data


def update_config(db: Session, cfg: ConfigSet, patch: dict, actor: str) -> ConfigSet:
    """按路径覆盖参数（点分路径，如 cost.materials 或 val1.wall_min_hard_mm），带审计由调用方记录。"""
    for path, value in patch.items():
        keys = path.split(".")
        node = cfg.data
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        node[keys[-1]] = value
    cfg.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(cfg)
    return cfg
