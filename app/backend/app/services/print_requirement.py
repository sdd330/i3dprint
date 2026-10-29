# E3DP backend — 打印需求（材料 / 强度 / 进阶参数）与「打印清单」
# ---------------------------------------------------------------------------
# 阶段说明（2026-10 调整）：在线切片与 Val2 切片核验**暂时停用**。
# 用户通过 Val1 后不再云端切片，而是填写打印需求（材料 + 强度 + 进阶参数），
# 平台把需求保存为结构化「清单」，交给执行打印的负责人按清单在 Bambu Studio 手动切片/打印。
# 因此这里只做两件事：
#   1) 把「强度档 + 进阶参数」合并成一份完整的工艺参数快照（与原 OrcaSlicer 字段同名）
#   2) 在没有切片器的前提下，用几何量做**估算**（标注为估算，不冒充切片结果）
# 恢复切片能力时：本模块参数可直接喂给 services/slicing.py，无需改动数据模型。

from __future__ import annotations

import math

# 强度档默认值：配置中心缺省时的兜底（活动配置 `strength_tiers` 存在时以配置为准）
# 字段名与 OrcaSlicer / AdvancedParamsForm 一致，便于执行人直接录入切片器
STRENGTH_TIERS = [
    {
        "id": "light", "name": "轻量", "icon": "🍃",
        "desc": "展示摆件、不承力：耗材省、速度快",
        "layer_height": 0.24, "wall_loops": 2, "infill_density": 10,
        "top_shell_layers": 3, "bottom_shell_layers": 3, "infill_pattern": "grid",
        "supports": "auto",
    },
    {
        "id": "standard", "name": "标准", "icon": "⚖️",
        "desc": "日常推荐：质量与强度均衡",
        "layer_height": 0.20, "wall_loops": 2, "infill_density": 20,
        "top_shell_layers": 4, "bottom_shell_layers": 3, "infill_pattern": "grid",
        "supports": "auto",
    },
    {
        "id": "strong", "name": "坚固", "icon": "🏗️",
        "desc": "功能件、受力件：更厚壁、更高填充",
        "layer_height": 0.20, "wall_loops": 3, "infill_density": 40,
        "top_shell_layers": 5, "bottom_shell_layers": 4, "infill_pattern": "gyroid",
        "supports": "auto",
    },
    {
        "id": "ultra", "name": "超坚固", "icon": "🛡️",
        "desc": "承力结构件：耗材与时间显著增加",
        "layer_height": 0.16, "wall_loops": 4, "infill_density": 60,
        "top_shell_layers": 6, "bottom_shell_layers": 5, "infill_pattern": "cubic",
        "supports": "auto",
    },
]

# 进阶参数基线（未填写时的兜底；也是 X1C 标准档基准）
BASE_ADVANCED = {
    "layer_height": 0.2, "initial_layer_print_height": 0.2,
    "wall_loops": 2, "top_shell_layers": 4, "bottom_shell_layers": 3,
    "infill_density": 20, "infill_pattern": "grid",
    "outer_wall_speed": 200, "inner_wall_speed": 300, "sparse_infill_speed": 270,
    "travel_speed": 500, "initial_layer_speed": 50,
    "nozzle_temperature": 220, "initial_layer_print_temperature": 220,
    "bed_temperature": 65, "initial_layer_bed_temperature": 65,
    "enable_support": "auto", "support_type": "normal(auto)", "support_threshold_angle": 30,
    "retraction_length": 0.8, "retraction_speed": 30, "z_hop": 0.4,
    "max_volumetric_speed": 21,
}

# 材料 → 温度基线（进阶参数未显式覆盖时按材料给默认值）
MATERIAL_TEMPS = {
    "pla": {"nozzle": 220, "bed": 65},
    "petg": {"nozzle": 250, "bed": 80},
    "abs": {"nozzle": 260, "bed": 100},
    "tpu": {"nozzle": 230, "bed": 50},
}

# 壳层占比经验值：外壳/顶底实心层约占模型体积的 30%（用于无切片器时的耗材估算）
SHELL_FRACTION = 0.30


def strength_tiers(cfg: dict | None) -> list[dict]:
    """活动生效的强度档（配置中心 `strength_tiers` 优先，缺失/为空时用代码默认值）。"""
    tiers = ((cfg or {}).get("strength_tiers") or [])
    tiers = [t for t in tiers if isinstance(t, dict) and (t.get("id") or "").strip()]
    return tiers or STRENGTH_TIERS


def tier_by_id(tier_id: str, cfg: dict | None = None) -> dict:
    tiers = strength_tiers(cfg)
    return next((t for t in tiers if t["id"] == tier_id), tiers[min(1, len(tiers) - 1)])


def merge_params(material_id: str, strength: str, advanced: dict | None, cfg: dict | None = None) -> dict:
    """强度档 + 进阶覆盖 → 完整工艺参数快照

    优先级：进阶参数（用户显式填写）> 强度档 > 材料温度基线 > 全局基线
    """
    tier = tier_by_id(strength, cfg)
    temps = MATERIAL_TEMPS.get(material_id, MATERIAL_TEMPS["pla"])
    base = dict(BASE_ADVANCED)
    base.update({"nozzle_temperature": temps["nozzle"],
                 "initial_layer_print_temperature": temps["nozzle"],
                 "bed_temperature": temps["bed"],
                 "initial_layer_bed_temperature": temps["bed"]})
    # 强度档的核心项生效（进阶没填时）；配置里缺字段就跳过，避免 KeyError
    for k in ("layer_height", "wall_loops", "infill_density", "top_shell_layers",
              "bottom_shell_layers", "infill_pattern"):
        if tier.get(k) is not None:
            base[k] = tier[k]
    merged = {**base, **(advanced or {})}
    merged["strength"] = tier["id"]
    merged["strength_name"] = tier["name"]
    merged["supports"] = tier.get("supports", "auto")
    return merged


def estimate(stats: dict, material: dict, params: dict) -> dict:
    """无切片器下的**估算**（明确标注估算，不冒充切片结果）

    耗材: 体积 × (壳层占比 + 填充占比) × 材料密度
    时长: 挤出体积 ÷ 体积流量 × 利用率系数 + 固定开销
    """
    volume_cm3 = float((stats or {}).get("volume_cm3") or 0)
    density = float(material.get("density") or 1.24)   # g/cm³
    infill = float(params.get("infill_density") or 20) / 100.0
    weight_g = volume_cm3 * (SHELL_FRACTION + (1 - SHELL_FRACTION) * infill) * density
    weight_g = round(max(weight_g, 0.0), 1)

    flow = float(params.get("max_volumetric_speed") or 21)       # mm³/s
    layer_h = float(params.get("layer_height") or 0.2)
    low_quality_factor = 1.0 + max(0.0, (0.20 - min(layer_h, 0.20))) * 6  # 层高越小越慢
    extruded_cm3 = weight_g / density if density else 0.0
    if flow > 0:
        minutes = extruded_cm3 / (flow * 60.0 / 1000.0) * 1.8 * low_quality_factor  # 1.8=路径/空驶利用率
    else:
        minutes = 0.0
    minutes = minutes + 4 if weight_g > 0 else 0            # 固定开销（预热/首层/退火）
    est_time_sec = int(math.ceil(minutes * 60)) if minutes else 0

    return {
        "source": "estimate",          # 估算，非切片结果
        "weight_g": weight_g,
        "time_sec": est_time_sec,
        "volume_cm3": round(volume_cm3, 2),
        "layer_height": layer_h,
        "note": "在线切片暂缓：耗材与时长由几何量估算，执行人可在切片器中复核",
    }


def build_manifest(order, material: dict, params: dict, est: dict, cfg: dict | None = None) -> dict:
    """打印清单（执行打印的负责人直接照着做的一页纸）"""
    tier = tier_by_id(params.get("strength") or "standard", cfg)
    geometry = order.geometry or {}
    return {
        "order_id": order.id,
        "name": order.name,
        "user": order.user.name if getattr(order, "user", None) else "",
        "model_id": order.model_id,
        "model_version_id": order.model_version_id,
        "bbox": geometry.get("bbox"),
        "volume_cm3": (order.val1 or {}).get("stats", {}).get("volume_cm3"),
        "material": {"id": material.get("id"), "name": material.get("name"),
                     "price_per_g": material.get("price_per_g"), "coeff": material.get("coeff")},
        "color": order.color,
        "strength": {"id": tier["id"], "name": tier["name"], "desc": tier["desc"]},
        "params": params,
        "estimate": est,
        "self_filament": bool(order.self_filament),
        "filament_approved": order.filament_approved,
        "operator_note": params.get("operator_note", ""),
        "val1": {
            "result": (order.val1 or {}).get("result"),
            "flagged": (order.val1 or {}).get("flagged"),
            "items": [i for i in (order.val1 or {}).get("items", []) if i.get("level") != "pass"],
        },
        "placement": order.placement,
    }
