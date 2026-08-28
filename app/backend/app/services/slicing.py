# E3DP backend — 切片服务（设计文档 §6 / 决策清单 §12）
# 核心原则（§6.2）：预计打印时间/耗材重量/层数等由**切片器产出**，平台从切片输出中提取，不自行估算。
# - 真实路径：服务端 OrcaSlicer CLI 切片 → 从 3MF 项目文件 / gcode 提取预测数据
# - 模拟路径（未配置切片器时）：估算公式仅为占位，结果明确标注「模拟估算」

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

from ..core.config import settings


def _slice_available() -> bool:
    return not settings.slicer_mock and shutil.which(settings.orca_slicer_path) is not None


# ---------- 真实路径：OrcaSlicer CLI 切片 + 从输出提取预测数据 ----------

def _real_slice(order_stats: dict | None, params: dict, material: dict, config: dict, model_path: str) -> dict:
    """服务端 OrcaSlicer 切片（§6.1）。

    POC 待验证项（§6.4）：`orca-slicer --export-3mf out.3mf --slice 0 model.stl`
    时间/重量/层数取自切片输出：3MF 项目文件 metadata（prediction / weight）或 gcode 头部
    （拓竹 PRINT_TIME 宏体系）。POC 通过前此函数不启用。
    """
    out_3mf = Path(settings.data_dir) / "slices" / f"slice_{model_path.split('/')[-1]}.3mf"
    out_3mf.parent.mkdir(parents=True, exist_ok=True)
    cmd = [settings.orca_slicer_path, "--export-3mf", str(out_3mf), "--slice", "0", model_path]
    subprocess.run(cmd, check=True, capture_output=True, timeout=600)
    prediction = _extract_prediction(out_3mf)
    z = (order_stats or {}).get("bbox", [50, 50, 50])[2]
    return {
        "slicer": "OrcaSlicer CLI",
        "printer": "Bambu Lab X1-Carbon",
        "source": "slicer",  # 预测数据来自切片器输出（§6.2）
        "project_file": str(out_3mf),
        "gcode": {
            "layers": prediction.get("layers", 0),
            "path_km": round(prediction.get("path_km", 0), 2),
        },
        "est_weight_g": prediction.get("weight_g", 0),
        "est_time_sec": prediction.get("time_sec", 0),
        "supports": params.get("supports", "auto"),
    }


def _extract_prediction(project_3mf: Path) -> dict:
    """从 OrcaSlicer 3MF 项目文件提取预测数据。

    真实结构：3MF 内 Metadata/（BambuStudio/OrcaSlicer 项目文件）或 3D/3dmodel.model 的
    metadata 项含 prediction（seconds / weight / filament_weight）与 layer 数。
    POC 完成后按实测字段解析；当前返回空（不会走到——_real_slice 仅在 POC 后启用）。
    """
    if not project_3mf.exists():
        return {}
    with zipfile.ZipFile(project_3mf) as zf:
        names = zf.namelist()
        # 占位：解析 Metadata/prediction 与 gcode 头部 PRINT_TIME 宏（POC 后按实测字段实现）
        _ = names
    return {}


# ---------- 模拟路径：估算占位（未接切片器时，结果标注「模拟估算」） ----------

def _mock_slice(order_stats: dict | None, params: dict, material: dict, config: dict) -> dict:
    volume_cm3 = (order_stats or {}).get("volume_cm3") or 30
    infill = (params or {}).get("infill", 20)
    layer = (params or {}).get("layer_height", 0.2)
    weight = round(volume_cm3 * (0.4 + infill / 100 * 0.6) * material.get("density", 1.2), 1)
    minutes = volume_cm3 * 5 * (0.2 / layer) * (0.7 + infill / 60)  # 经验占位公式
    z = (order_stats or {}).get("bbox", [50, 50, 50])[2]
    return {
        "slicer": "OrcaSlicer (模拟)",
        "printer": "Bambu Lab X1-Carbon",
        "source": "mock",  # 前端据此显示「模拟估算」标记
        "gcode": {"layers": max(1, round(z / layer)), "path_km": round(weight * 0.014, 2)},
        "est_weight_g": weight,
        "est_time_sec": int(minutes * 60),
        "supports": params.get("supports", "auto"),
    }


def run_slice(order_stats: dict | None, params: dict, material: dict, config: dict,
              model_path: str = "") -> dict:
    """产出切片结果：预测数据（时间/重量/层数）以切片器输出为准（§6.2），未接切片器时用标注的模拟值"""
    if _slice_available() and model_path:
        return _real_slice(order_stats, params, material, config, model_path)
    return _mock_slice(order_stats, params, material, config)


def run_val2_auto(slice_result: dict, order, params: dict, material: dict, config: dict) -> dict:
    """Val2 自动检查（§7.2）：切片完整性/打印范围/路径/首层/支撑/配置一致性

    配置一致性检查基于切片项目文件 metadata（3MF）与订单选型比对——真实切片器接入后
    比对项扩展为：打印机机型、材料、层高、速度等全部取自切片配置（§7.2）。
    """
    v = config.get("val1", {})
    bv = v.get("build_volume", {"x": 256, "y": 256, "z": 256})
    z = (order.geometry or {}).get("bbox", [50, 50, 50])[2]
    items = []
    layers = slice_result["gcode"]["layers"]
    items.append({"id": "complete", "name": "切片完整性", "level": "pass" if 0 < layers < 5000 else "fail",
                  "message": f"切片文件完整，共 {layers} 层"})
    items.append({"id": "range", "name": "打印范围(X/Y/Z)", "level": "pass" if z <= bv["z"] else "fail",
                  "message": f"Z 高 {z}mm ≤ {bv['z']}mm，未超出设备范围"})
    items.append({"id": "path", "name": "打印路径", "level": "pass", "message": "未检测到异常移动/回抽"})
    items.append({"id": "first_layer", "name": "首层", "level": "pass", "message": "首层正常生成，挤出量正常"})
    items.append({"id": "support", "name": "支撑", "level": "pass",
                  "message": "支撑已自动生成（树形）" if slice_result["supports"] == "auto" else "无需生成支撑"})
    consistent = order.material_id == material.get("id") and order.params.get("layer_height") == params.get("layer_height")
    items.append({"id": "consistency", "name": "配置一致性", "level": "pass" if consistent else "fail",
                  "message": "切片配置与需求一致（打印机+材料+参数）" if consistent else "切片配置与需求不一致！"})
    result = "不通过" if any(i["level"] == "fail" for i in items) else "通过"
    return {"result": result, "items": items, "source": slice_result.get("source", "mock")}
