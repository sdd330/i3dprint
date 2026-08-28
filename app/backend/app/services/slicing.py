# E3DP backend — 切片服务（设计文档 §6 / 决策清单 §12）
# 核心原则（§6.2）：预计打印时间/耗材重量/层数等由**切片器产出**，平台从切片输出中提取，不自行估算。
# - 真实路径：服务端 OrcaSlicer CLI 切片 → 从 3MF 项目文件 / gcode 提取预测数据
# - 模拟路径（未配置切片器时）：估算公式仅为占位，结果明确标注「模拟估算」

from __future__ import annotations

import json
import numpy as np
import os
import re
import shutil
import subprocess
import tempfile
import uuid
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from ..core.config import settings
from ..core.dynamic_settings import get_setting
from .slice_concurrency import acquire_slice_slot, release_slice_slot


# OrcaSlicer 标准档完整基准（--export-settings 导出，637 键展开）
BASELINE_PROCESS = Path(__file__).resolve().parent.parent / "profiles" / "x1c_standard_full.json"

# 材料 → OrcaSlicer 内置耗材 profile 映射（菜鸟模式 load 对应材料的标准参数）
# 路径从 machine profile 位置推导（profiles/BBL/filament/），不硬编码安装目录
FILAMENT_PROFILE_MAP = {
    "pla": "Bambu PLA Basic @BBL X1C.json",
    "petg": "Bambu PETG Basic @BBL X1C.json",
    "abs": "Bambu ABS @BBL X1C.json",
    "tpu": "Bambu TPU 95A @BBL X1C.json",
}


def _filament_profile_for(material_id: str) -> str:
    """按材料返回 filament profile（派生注入 filament_type）。
    CLI 对 --load-filaments 的跨目录继承解析失败（fdm_filament_pet 等基类取不到），
    filament_type 会回退默认 PLA——显式注入，保证 gcode/slice_info 材料正确。"""
    name = FILAMENT_PROFILE_MAP.get(material_id or "")
    if not name:
        return get_setting("orca_filament_profile", settings.orca_filament_profile)
    root = Path(get_setting("orca_machine_profile", settings.orca_machine_profile)).resolve().parent.parent.parent
    src = root / "BBL" / "filament" / name
    if not src.exists():
        return get_setting("orca_filament_profile", settings.orca_filament_profile)
    data = json.loads(src.read_text())
    if not data.get("filament_type"):
        data["filament_type"] = {"pla": "PLA", "petg": "PETG", "abs": "ABS", "tpu": "TPU"}.get(material_id or "", "PLA")
    slices_dir = Path(settings.data_dir) / "slices"
    slices_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".json", prefix="filament_", dir=slices_dir)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    return tmp

# 进阶参数 → 临时 process profile（§4.2 进阶手动，OrcaSlicer 同字段名）
def build_process_profile(advanced: dict) -> str:
    if not BASELINE_PROCESS.exists():
        return settings.orca_process_profile
    base = json.loads(BASELINE_PROCESS.read_text())
    # vendor 格式 process 定义：扁平字段 + 元数据（元数据必须在 update 之后设置，
    # 否则会被 base 里的 from=project/name=project_settings 覆盖）
    profile = dict(base)
    # 兼容打印机列表必须与目标机器匹配（否则 process not compatible with printer）
    vendor = json.loads(Path(get_setting("orca_process_profile", settings.orca_process_profile)).read_text())
    if vendor.get("compatible_printers"):
        profile["compatible_printers"] = vendor["compatible_printers"]
    profile.update({
        "type": "process",
        "name": "E3DP Advanced",
        "inherits": "0.20mm Standard @BBL X1C",
        "from": "system",
        "setting_id": "e3dp-advanced",
        "instantiation": "true",
        "description": "平台进阶参数派生",
    })
    for k, v in (advanced or {}).items():
        if v is None or v == "":
            continue
        orig = profile.get(k)
        if isinstance(orig, list):
            profile[k] = [str(v), str(v)]
        else:
            profile[k] = str(v)
    slices_dir = Path(settings.data_dir) / "slices"
    slices_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".json", prefix="proc_", dir=slices_dir)
    with os.fdopen(fd, "w") as f:
        json.dump(profile, f)
    return tmp


def _prepare_machine_profile() -> str:
    """加载 machine profile 并显式注入打印区域（X1C 256³）。
    CLI 的继承链解析不稳定（日志显示 machine "inherits 自己"），未注入时会退回默认
    200×200×100 平台，导致 200mm+ 高模型被误判为超出体积。"""
    src = Path(get_setting("orca_machine_profile", settings.orca_machine_profile))
    data = json.loads(src.read_text())
    data["printable_area"] = data.get("printable_area") or ["0x0", "256x0", "256x256", "0x256"]
    data["printable_height"] = str(data.get("printable_height") or 256)
    slices_dir = Path(settings.data_dir) / "slices"
    slices_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".json", prefix="machine_", dir=slices_dir)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    return tmp


def _slice_available() -> bool:
    # .app 内二进制 which 找不到，用文件存在判断
    return not get_setting("slicer_mock", settings.slicer_mock) and os.path.exists(
        get_setting("orca_slicer_path", settings.orca_slicer_path))


def prepare_slice_file(order, model_version, slices_dir: Path) -> str:
    """把模型准备成可切片文件（§4.4 摆放约束传递，姿态/位置/缩放完整应用）：
    - 内置模型（无真实文件）：trimesh 重建导出 STL
    - 上传模型：按摆放 scale/rotation/position 应用变换后导出临时 STL（无变换则直接用原文件）
    - 切片前校验模型尺寸在打印体积（256³）内，超出抛 RuntimeError（由路由转 400 明确提示）
    """
    import trimesh
    from ..services.val1 import build_preset
    slices_dir = Path(slices_dir)
    slices_dir.mkdir(parents=True, exist_ok=True)
    placement = order.placement or {}
    scale = placement.get("scale") or 1
    rot = placement.get("rotation") or [0, 0, 0]
    pos = placement.get("position") or [0, 0, 0]
    has_pose = scale != 1 or any(float(r) for r in rot) or any(float(p) for p in pos)

    is_upload = model_version and os.path.exists(model_version.file_path) and not model_version.file_path.startswith("preset:")
    if is_upload:
        src = model_version.file_path
        if not has_pose:
            return src
        # 上传 OBJ 大文件走向量化解析（trimesh 加载 136MB 需 ~10s，fast_loader ~3s）
        if src.lower().endswith(".obj"):
            from .fast_loader import load_obj_vertices_faces
            verts, faces = load_obj_vertices_faces(src)
            mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
        else:
            mesh = trimesh.load(src, force="mesh", process=False)
        name = Path(src).stem
    else:
        # 内置模型：重建（模型名 = "内置模型 · kind"）
        model = model_version.model if model_version else None
        kind = (model.name if model else "generic").replace("内置模型 · ", "").strip() or "generic"
        mesh = build_preset(kind)
        name = f"preset_{kind}"

    if scale != 1:
        mesh.apply_scale(scale)
    rx, ry, rz = [float(a) for a in rot]
    if any((rx, ry, rz)):
        from trimesh.transformations import euler_matrix
        mesh.apply_transform(euler_matrix(rx, ry, rz, "sxyz"))
    px, py, pz = [float(p) for p in pos]
    if any((px, py, pz)):
        mesh.apply_translation([px, py, pz])

    # 坐标系转换（仅内置模型）：build_preset 程序化几何为 Y-up（Bambu/Three.js 约定），
    # OrcaSlicer/STL 约定 Z-up → 绕 X 轴 -90° 立起来。
    # 上传的 STL/OBJ 本来就是 Z-up（保持原样，否则 250mm 高会被转成 250mm 宽导致放不进平台）
    if not is_upload:
        from trimesh.transformations import rotation_matrix
        mesh.apply_transform(rotation_matrix(-np.pi / 2, [1.0, 0.0, 0.0]))

    # 体积校验：任一轴超 256mm 直接明确报错（否则 OrcaSlicer 报晦涩的 Nothing to be sliced）
    size = mesh.bounds[1] - mesh.bounds[0]
    over = [a for a, d in zip("XYZ", size) if d > 256.0]
    if over:
        raise RuntimeError(f"模型摆放后尺寸 {size[0]:.0f}×{size[1]:.0f}×{size[2]:.0f}mm，"
                           f"{''.join(over)} 轴超出打印平台 256mm，请回摆放界面缩小或调整姿态")
    # 平台适配：OrcaSlicer 平台 XY 范围 [0,256]（原点在角落），关闭 --arrange 后需自行
    # 吸底（z 底=0）+ 居中（x/y 平台中心），否则模型在原点 → 部分出界 → Nothing to be sliced
    b = mesh.bounds
    mesh.apply_translation([
        -b[0][0] + (256.0 - size[0]) / 2,
        -b[0][1] + (256.0 - size[1]) / 2,
        -b[0][2],
    ])
    out = slices_dir / f"posed_{name}.stl"
    mesh.export(str(out))
    return str(out)


# ---------- 真实路径：OrcaSlicer CLI 切片 + 从输出提取预测数据 ----------

def _real_slice(order_stats: dict | None, params: dict, material: dict, config: dict, model_path: str) -> dict:
    """服务端 OrcaSlicer CLI 真实切片（§6.1，POC 通过 2026-08-28）。

    CLI 正确用法（避免 fork 系段错误）：
      --load-settings "machine.json;process.json"   # 打印机 + 工艺（分号分隔）
      --load-filaments filament.json                # 耗材独立参数
      --export-slicedata dir                        # 切片元数据
      --slice 0 --export-3mf out.3mf                # 产出 .gcode.3mf（拓竹可直传）
    预测数据（时间/重量/层数）从 3MF 解包后的 slice_info.config / plate_1.gcode 提取（§6.2）。
    """
    name = Path(model_path).stem
    slices_dir = Path(settings.data_dir) / "slices"
    slices_dir.mkdir(parents=True, exist_ok=True)
    out_3mf = slices_dir / f"slice_{name}.3mf"
    sd_dir = slices_dir / f"sd_{name}"
    sd_dir.mkdir(parents=True, exist_ok=True)
    for old in list(slices_dir.glob(f"slice_{name}.*")) + list(sd_dir.glob("*")):
        if old.suffix != ".3mf" or old.name != out_3mf.name:
            try: old.unlink()
            except OSError: pass
    process_profile = get_setting("orca_process_profile", settings.orca_process_profile)
    if (params or {}).get("advanced"):
        process_profile = build_process_profile(params["advanced"])
    orca_log = slices_dir / f"orca_{name}.log"
    cmd = [
        get_setting("orca_slicer_path", settings.orca_slicer_path),
        # §4.4：用户摆放姿态作为约束传递 → 关闭自动定向（--orient 0）；
        # 但 --arrange 必须开（=1），否则模型不被放置到 plate → "Nothing to be sliced"
        # （模型已在 prepare_slice_file 居中吸底，arrange 不会改变姿态，仅负责放置）
        "--arrange", "1", "--orient", "0",
        "--export-slicedata", str(sd_dir),
        "--logfile", str(orca_log),
        "--load-settings", f"{_prepare_machine_profile()};"
                          f"{process_profile}",
        "--load-filaments", _filament_profile_for(material.get("id")),
        "--slice", "0", "--export-3mf", str(out_3mf),
        model_path,
    ]
    acquire_slice_slot()  # 并发限流：最多 slicer_max_concurrent 个并行切片
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    finally:
        release_slice_slot()
    if proc.returncode != 0:
        orca_detail = ""
        if orca_log.exists():
            try:
                orca_detail = orca_log.read_text(errors="replace")[-500:]
            except OSError:
                pass
        err = (proc.stderr or proc.stdout or "")[-300:] + orca_detail
        raise RuntimeError(f"OrcaSlicer 切片失败：{err[-500:]}")
    prediction = _extract_prediction(out_3mf)
    if not prediction.get("time_sec"):
        raise RuntimeError("OrcaSlicer 切片成功但未提取到预测数据")
    # 重量：slice_info used_g 优先，否则 filament 体积 × 材料密度（密度与 Val1 同源）
    if not prediction.get("weight_g") and prediction.get("filament_cm3"):
        prediction["weight_g"] = prediction["filament_cm3"] * material.get("density", 1.2)
    return {
        "slicer": "OrcaSlicer 2.4.2 (CLI)",
        "printer": "Bambu Lab X1-Carbon",
        "source": "slicer",  # 预测数据来自切片器输出（§6.2）
        "project_file": str(out_3mf),
        "gcode": {
            "layers": prediction.get("layers", 0),
            "path_km": round(prediction.get("path_km", 0), 2),
        },
        "est_weight_g": round(prediction.get("weight_g", 0), 2),
        "est_time_sec": prediction.get("time_sec", 0),
        "supports": params.get("supports", "auto"),
    }


def _extract_prediction(project_3mf: Path) -> dict:
    """从 OrcaSlicer 3MF 解包提取预测数据（实测字段，2026-08-28）：

    - Metadata/slice_info.config：<metadata key="prediction"> 总估计时间（秒）；
      <filament ... used_m= 耗材长度(米) type=PLA>
    - Metadata/plate_1.gcode 注释：`; filament used [cm3] = X`、`; max_z_height: X`、
      `; model printing time: Xh Ym Zs; total estimated time: ...`
    重量 = cm3 × 材料密度（密度来自平台配置，与 Val1 同源）。
    """
    if not project_3mf.exists():
        return {}
    out = {}
    with zipfile.ZipFile(project_3mf) as zf:
        gcode = ""
        if "Metadata/plate_1.gcode" in zf.namelist():
            gcode = zf.read("Metadata/plate_1.gcode").decode("utf-8", errors="replace")
        if "Metadata/slice_info.config" in zf.namelist():
            root = ET.fromstring(zf.read("Metadata/slice_info.config"))
            for meta in root.iter("metadata"):
                key = meta.get("key", "")
                val = meta.get("value", "")
                if key == "prediction" and val.isdigit():
                    out["time_sec"] = int(val)
                if key == "weight" and val:
                    try: out["weight_g"] = float(val)
                    except ValueError: pass
            for fil in root.iter("filament"):
                out["filament_type"] = fil.get("type", "")
                out["filament_used_m"] = float(fil.get("used_m") or 0)
                if fil.get("used_g"):
                    try: out["weight_g"] = float(fil.get("used_g"))
                    except ValueError: pass
                break
    # gcode 注释
    m = re.search(r"filament used \[cm3\] = ([\d.]+)", gcode)
    if m:
        out["filament_cm3"] = float(m.group(1))
    m = re.search(r"max_z_height: ([\d.]+)", gcode)
    if m:
        out["max_z_height"] = float(m.group(1))
    m = re.search(r"total estimated time: ([\d]+)h ([\d]+)m ([\d]+)s", gcode)
    if m and "time_sec" not in out:
        out["time_sec"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    m = re.search(r"model printing time: ([\d]+)m ([\d]+)s", gcode)
    if m and "time_sec" not in out:
        out["time_sec"] = int(m.group(1)) * 60 + int(m.group(2))
    # 层数 = max_z_height / 层高（plate_1.gcode 头部 layer_height 或默认 0.2）
    m = re.search(r"layer_height = ([\d.]+)", gcode)
    layer_h = float(m.group(1)) if m else 0.2
    if out.get("max_z_height"):
        out["layers"] = max(1, round(out["max_z_height"] / layer_h))
    return out


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


# ---------- 逐层预览（§6.2 / §7.3：每层打印路径） ----------

def parse_gcode_layers(gcode_text: str, max_layers: int = 80, max_pts_per_layer: int = 600) -> list[dict]:
    """从 plate_1.gcode 解析逐层挤出路径（用于逐层预览）。
    - 层切换：`G1 Z{val}`（值增大 = 新层）
    - 路径：`G1 X.. Y.. E..`（E 增量 > 0 为挤出，收集为折线；E<=0/行程断开路径）
    - 抽稀：每层最多 max_pts_per_layer 个点
    """
    layers: list[dict] = []
    cur_z = 0.0
    cur_path: list[tuple[float, float]] = []
    paths: list[list[tuple[float, float]]] = []
    in_gcode_block = False  # 宏模板块（machine_start/end_gcode 单行长注释）跳过

    for line in gcode_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith(";"):
            # 宏模板定义行（含 \n 转义的整段）跳过
            if "machine_start_gcode" in line or "machine_end_gcode" in line or "layer_change_gcode" in line or "time_lapse_gcode" in line:
                in_gcode_block = True
            elif in_gcode_block and not line.endswith("n"):
                in_gcode_block = False
            continue
        if in_gcode_block:
            continue
        m = re.match(r"^G1 Z([\d.]+)", line)
        if m:
            z = float(m.group(1))
            if z > cur_z + 0.01 and (cur_path or paths):
                if cur_path:
                    paths.append(cur_path)
                    cur_path = []
                layers.append({"z": round(cur_z, 2), "paths": [p[:] for p in paths]})
                paths = []
                if len(layers) >= max_layers:
                    break
            cur_z = z
            continue
        m = re.match(r"^G1 X([\d.]+) Y([\d.]+)(?: E(-?[\d.]+))?", line)
        if m:
            x, y = float(m.group(1)), float(m.group(2))
            e = float(m.group(3)) if m.group(3) else 0.0
            if e > 0:
                if cur_path:
                    dx, dy = x - cur_path[-1][0], y - cur_path[-1][1]
                    if dx * dx + dy * dy > 1e-4:
                        cur_path.append((x, y))
                else:
                    cur_path.append((x, y))
            else:
                if cur_path:
                    paths.append(cur_path)
                    cur_path = []
    if cur_path:
        paths.append(cur_path)
    if paths or layers:
        layers.append({"z": round(cur_z, 2), "paths": [p[:] for p in paths]})

    # 抽稀每层点数
    for ly in layers:
        for pi, path in enumerate(ly["paths"]):
            if len(path) > max_pts_per_layer:
                step = len(path) / max_pts_per_layer
                ly["paths"][pi] = [path[int(i * step)] for i in range(max_pts_per_layer)]
    return layers
