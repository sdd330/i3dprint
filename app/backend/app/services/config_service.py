# E3DP backend — 配置中心服务（决策清单 §14：默认模板 + 活动副本可选继承 + 修改审计）

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from ..models import Campaign, ConfigAudit, ConfigTemplate

CATEGORIES = ["activity", "fee", "val1", "presets", "strength_tiers", "print", "compliance", "qa"]


def get_default_template(db: Session) -> ConfigTemplate:
    tpl = db.query(ConfigTemplate).filter_by(is_default=True).first()
    if not tpl:
        tpl = db.query(ConfigTemplate).first()
    return tpl


def _merge_defaults(value, default):
    """把默认值补进缺失的键（递归；已有值一律保留，不覆盖用户配置）。"""
    if isinstance(default, dict) and isinstance(value, dict):
        out = dict(default)
        for k, v in value.items():
            out[k] = _merge_defaults(v, default.get(k))
        return out
    if value is None:
        return default
    return value


def get_activity_config(db: Session, campaign: Campaign) -> dict:
    """活动参数副本；缺失分类/子键时回退默认模板（保证旧活动、旧模板兼容新增配置项）。"""
    cfg = dict(campaign.config or {})
    tpl = get_default_template(db)
    if not tpl:
        return cfg
    for cat in CATEGORIES:
        if cat not in cfg:
            cfg[cat] = tpl.data.get(cat)
        else:
            # 老数据缺新键（如 print.printers / strength_tiers）→ 用模板默认值补齐
            cfg[cat] = _merge_defaults(cfg.get(cat), tpl.data.get(cat))
    return cfg


def clone_config_for_campaign(db: Session, source: str = "template", source_campaign_id: int | None = None) -> dict:
    """新建活动时复制参数副本（可选继承：template 或上一场活动），并标注来源（决策清单 §14）"""
    if source == "previous" and source_campaign_id:
        prev = db.get(Campaign, source_campaign_id)
        base = dict(prev.config) if prev else {}
    else:
        tpl = get_default_template(db)
        base = dict(tpl.data) if tpl else {}
    out = {}
    sources: dict[str, str] = {}
    for cat in CATEGORIES:
        if cat in base:
            out[cat] = base[cat]
            sources[cat] = "template" if source == "template" else "previous"
    out["_sources"] = sources
    return out


def set_category(db: Session, scope: str, target_id: int | None, category: str, data,
                 operator: str = "", template: ConfigTemplate | None = None, campaign: Campaign | None = None):
    """更新模板或活动的某个分类参数，记录修改审计（§14 改动即时生效）"""
    if scope == "template":
        tpl = template or get_default_template(db)
        old = dict(tpl.data)
        tpl.data = {**old, category: data}
    else:
        cfg = dict(campaign.config or {})
        old = dict(cfg)
        sources = dict(cfg.get("_sources", {}))
        sources[category] = "custom"
        cfg = {**cfg, category: data, "_sources": sources}
        campaign.config = cfg
    db.add(ConfigAudit(
        scope=scope, target_id=target_id, category=category, path=category,
        old_value=json.dumps(old.get(category), ensure_ascii=False)[:1000],
        new_value=json.dumps(data, ensure_ascii=False)[:1000],
        operator=operator,
    ))
    db.commit()


def get_sources(campaign: Campaign) -> dict:
    cfg = campaign.config or {}
    return cfg.get("_sources", {})
