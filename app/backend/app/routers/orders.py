# E3DP backend — 打印需求（订单）主链路由（设计文档 §4-§11 / §12.2）

from __future__ import annotations

import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from pathlib import Path
from ..core.database import get_db
from ..core.dynamic_settings import get_setting
from ..core.security import client_ip, get_current_user, write_audit
from ..models import Campaign, CostLedger, Issue, Model, ModelVersion, Order, PrintJob, Review, User
from ..models.permissions import PERMISSIONS
from ..services.config_service import get_activity_config
from ..services.cost import settle_order_costs
from ..services.slicing import parse_gcode_layers, prepare_slice_file, run_slice, run_val2_auto
from ..services.slice_concurrency import slice_queue_stats
from ..services.state_machine import StateError, assert_campaign_open, transition
from ..services.val1 import analyze_file, build_preset, run_val1
from .auth import _user_out

router = APIRouter()

DbDep = Annotated[Session, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]


# 几何分析：独立子进程执行（trimesh 持 GIL，线程池超时杀不掉 → 改进程隔离，见 analysis_worker）
from ..services.analysis_worker import analyze_with_timeout as _analyze_with_timeout


def get_order_or_403(db: Session, order_id: int, user: User) -> Order:
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="需求不存在")
    if user.role.code != "admin" and order.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问他人的需求")
    return order


def _order_out(db: Session, o: Order) -> dict:
    return {
        "id": o.id, "name": o.name, "status": o.status, "campaign_id": o.campaign_id,
        "model_id": o.model_id, "model_version_id": o.model_version_id,
        "model_name": db.get(Model, o.model_id).name if o.model_id else None,
        "material_id": o.material_id, "color": o.color, "params": o.params,
        "placement": o.placement, "geometry": o.geometry,
        "val1": o.val1, "slice": o.slice, "val2auto": o.val2auto,
        "self_filament": o.self_filament, "filament_approved": o.filament_approved,
        "reprint_rate": o.reprint_rate,
        "appeal": o.appeal, "feedback": o.feedback, "cost": o.cost,
        "timeline": o.timeline, "created_at": o.created_at,
        "print_jobs": [_job_out(j) for j in o.print_jobs],
        "issues": [{"id": i.id, "stage": i.stage, "type": i.type, "description": i.description, "status": i.status} for i in o.issues],
        "reviews": [{"stage": r.stage, "result": r.result, "reviewer": r.reviewer, "note": r.note, "at": r.at} for r in o.reviews],
        "ledger": [{"kind": c.kind, "amount": c.amount, "reason": c.reason, "at": c.at}
                    for c in db.query(CostLedger).filter_by(order_id=o.id).all()],
    }


def _job_out(j: PrintJob) -> dict:
    from ..services.print_service import progress
    return {
        "id": j.id, "seq": j.seq, "printer_id": j.printer_id, "status": j.status,
        "est_time_sec": j.est_time_sec, "est_weight_g": j.est_weight_g, "actual_weight_g": j.actual_weight_g,
        "gcode": j.gcode, "started_at": j.started_at, "ended_at": j.ended_at,
        "note": j.note, "progress": progress(j),
    }


def _material_from_config(config: dict, material_id: str) -> dict:
    for m in config.get("fee", {}).get("materials", []):
        if m["id"] == material_id:
            return m
    raise HTTPException(status_code=400, detail="材料不存在")


class SelectModelIn(BaseModel):
    model_id: int | None = None
    preset_kind: str | None = None  # 内置演示模型（vase/robot/stand/spinner/penholder/generic）


class PlacementIn(BaseModel):
    placement: dict
    geometry: dict  # 前端分析报告（bbox/体积等）；服务端以 trimesh 真实分析为准兜底
    self_filament: bool = False
    # 材料/参数在 Val1 通过后选择（§4.1），摆放提交不再需要


class ResubmitIn(BaseModel):
    placement: dict
    geometry: dict
    material_id: str = "pla"
    color: str = "#E8602C"
    params: dict


class ResliceIn(BaseModel):
    params: dict
    material_id: str = "pla"
    color: str = "#E8602C"


# ---------- 列表 / 创建 ----------

@router.get("/orders")
def list_orders(db: DbDep, user: UserDep):
    q = db.query(Order)
    if user.role.code != "admin":
        q = q.filter_by(user_id=user.id)
    orders = q.order_by(Order.id.desc()).all()
    return {"orders": [_order_out(db, o) for o in orders]}


@router.post("/orders")
def create_order(db: DbDep, user: UserDep, request: Request, body: dict | None = None):
    campaign = db.query(Campaign).order_by(Campaign.id.desc()).first()
    if not campaign:
        raise HTTPException(status_code=409, detail="暂无活动")
    try:
        assert_campaign_open(campaign)
    except StateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    order = Order(campaign_id=campaign.id, user_id=user.id,
                  name=(body or {}).get("name") or "新打印需求")
    db.add(order)
    db.commit()
    db.refresh(order)
    entry = transition(order, "draft", "创建打印需求")
    db.commit()
    write_audit(db, user, "order.create", target=f"O{order.id}", ip=client_ip(request))
    return {"order": _order_out(db, order)}


@router.get("/orders/{order_id}")
def get_order(order_id: int, db: DbDep, user: UserDep):
    order = get_order_or_403(db, order_id, user)
    return {"order": _order_out(db, order)}


@router.get("/models/{version_id}/file")
def model_file(version_id: int, db: DbDep, user: UserDep):
    """模型文件下载（摆放工作区三维预览用；归属校验：只能取自己模型或负责人）"""
    mv = db.get(ModelVersion, version_id)
    if not mv or not mv.file_path or mv.file_path.startswith("preset:"):
        raise HTTPException(status_code=404, detail="模型文件不存在")
    model = db.get(Model, mv.model_id)
    if user.role.code != "admin" and (not model or model.owner_id != user.id):
        raise HTTPException(status_code=403, detail="无权访问该模型文件")
    ext = os.path.splitext(mv.file_path)[1].lower()
    media = "model/obj" if ext == ".obj" else "application/sla"
    return FileResponse(mv.file_path, media_type=media, filename=f"model{ext}")


# ---------- 模型选择 / 上传 ----------

@router.post("/orders/{order_id}/select-model")
def select_model(order_id: int, body: SelectModelIn, db: DbDep, user: UserDep):
    order = get_order_or_403(db, order_id, user)
    if order.status not in ("draft", "modeling", "val1_failed", "rework", "val2_failed"):
        raise HTTPException(status_code=409, detail="当前状态不能更换模型")
    if body.preset_kind:
        # 内置演示模型：程序化生成 + 真实 trimesh 分析
        mesh = build_preset(body.preset_kind)
        from ..services.val1 import analyze_mesh
        stats = analyze_mesh(mesh)
        model = Model(owner_id=user.id, name=f"内置模型 · {body.preset_kind}", kind="preset",
                      description="程序化演示模型")
        db.add(model)
        db.flush()
        version = ModelVersion(model_id=model.id, version=1, file_path=f"preset:{body.preset_kind}",
                               stats=stats, checks={})
        db.add(version)
        db.flush()
        order.model_id, order.model_version_id = model.id, version.id
    elif body.model_id:
        order.model_id = body.model_id
        mv = db.query(ModelVersion).filter_by(model_id=body.model_id).order_by(ModelVersion.version.desc()).first()
        order.model_version_id = mv.id if mv else None
    else:
        raise HTTPException(status_code=400, detail="请选择模型或指定内置模型")
    name = db.get(Model, order.model_id).name
    order.name = name
    transition(order, "modeling", f"选择模型「{name}」，进入摆放调整")
    db.commit()
    return {"order": _order_out(db, order)}


@router.post("/orders/{order_id}/upload")
def upload_model(order_id: int, file: UploadFile, db: DbDep, user: UserDep):
    """上传模型（sync def：读取+几何分析在 FastAPI 线程池执行；
    分析走独立子进程，主进程 GIL/event loop 均不被阻塞——大文件分析期间其他请求正常响应）"""
    order = get_order_or_403(db, order_id, user)
    if order.status not in ("draft", "modeling", "val1_failed", "rework", "val2_failed"):
        raise HTTPException(status_code=409, detail="当前状态不能上传模型")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".stl", ".obj"):
        raise HTTPException(status_code=400, detail="仅支持 STL / OBJ 文件")
    from ..core.config import settings
    data = file.file.read()  # UploadFile.file 为 SpooledTemporaryFile（同步读）
    if len(data) > get_setting("max_upload_bytes", settings.max_upload_bytes):
        raise HTTPException(status_code=413, detail=f"文件过大（{len(data) / 1024 / 1024:.0f}MB），限制 {settings.max_upload_bytes / 1024 / 1024:.0f}MB")
    fname = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(settings.upload_dir, fname)
    with open(path, "wb") as f:
        f.write(data)
    stats = _analyze_with_timeout(path, int(get_setting("analysis_timeout_sec", settings.analysis_timeout_sec)))
    if stats.get("error"):
        raise HTTPException(status_code=400, detail=stats["error"])
    if not stats.get("face_count"):
        raise HTTPException(status_code=400, detail="模型文件解析失败，请检查文件完整性（支持 STL/OBJ）")
    model = Model(owner_id=user.id, name=os.path.splitext(file.filename or "模型")[0], kind="upload")
    db.add(model)
    db.flush()
    version = ModelVersion(model_id=model.id, version=1, file_path=path, stats=stats, checks={})
    db.add(version)
    db.flush()
    order.model_id, order.model_version_id = model.id, version.id
    order.name = model.name
    transition(order, "modeling", f"上传模型「{model.name}」（{stats.get('face_count', 0):,} 面），进入摆放调整")
    db.commit()
    return {"order": _order_out(db, order), "stats": stats}


class PlacementSaveIn(BaseModel):
    placement: dict
    geometry: dict


@router.post("/orders/{order_id}/placement-preview")
def save_placement_preview(order_id: int, body: PlacementSaveIn, db: DbDep, user: UserDep):
    """仅保存摆放结果（不触发 Val1）：工作区保存 → 跳参数配置页（摆放与参数分两界面）"""
    order = get_order_or_403(db, order_id, user)
    if order.status not in ("draft", "modeling", "val1_failed"):
        raise HTTPException(status_code=409, detail="当前状态不能保存摆放")
    order.placement = body.placement
    order.geometry = body.geometry
    db.commit()
    return {"order": _order_out(db, order)}


# ---------- 摆放提交 → Val1 → 切片 → Val2 自动检查 ----------

@router.post("/orders/{order_id}/placement")
def submit_placement(order_id: int, body: PlacementIn, db: DbDep, user: UserDep):
    """摆放提交 → Val1（§4.1：摆放 → Val1 → 耗材/参数 → 切片）。
    Val1 只依赖摆放后的几何（trimesh），不需要耗材/切片参数；通过后进入切片环节（等参数页提交）。"""
    order = get_order_or_403(db, order_id, user)
    if order.status not in ("modeling", "val1_failed"):
        raise HTTPException(status_code=409, detail="当前状态不能提交摆放")
    if not order.model_version_id:
        raise HTTPException(status_code=400, detail="请先选择或上传模型")
    order.placement = body.placement
    order.geometry = body.geometry
    order.self_filament = body.self_filament  # 材料/参数在 Val1 通过后选择（§4.1）

    config = get_activity_config(db, order.campaign)
    transition(order, "val1_pending", "提交 Val1 自动审核")
    # 几何数据以服务端 trimesh 真实分析为准（模型版本 stats）；前端仅覆盖摆放后的 bbox（方向/尺寸约束，§4.4）
    mv = db.get(ModelVersion, order.model_version_id) if order.model_version_id else None
    stats = dict(mv.stats) if mv and mv.stats else dict(body.geometry or {})
    # 摆放缩放换算：壁厚/体积/表面积随 scale 线性/立方缩放（否则单位或缩放后的几何量失真，
    # 例：±0.5 坐标的模型放大 100 倍打印时，壁厚/体积必须按 scale 换算后再过 Val1）
    scale = float((body.placement or {}).get("scale") or 1)
    if scale != 1:
        if stats.get("bbox"):
            stats["bbox"] = [round(b * scale, 2) for b in stats["bbox"]]
        if stats.get("min_wall") is not None:
            stats["min_wall"] = round(stats["min_wall"] * scale, 2)
        if stats.get("volume_cm3"):
            stats["volume_cm3"] = round(stats["volume_cm3"] * scale ** 3, 2)
        if stats.get("surface_cm2"):
            stats["surface_cm2"] = round(stats["surface_cm2"] * scale ** 2, 1)
    if body.geometry and body.geometry.get("bbox"):
        stats["bbox"] = body.geometry["bbox"]
    val1 = run_val1(stats, config)  # 纯几何判定，不依赖耗材/切片参数
    order.val1 = val1
    db.add(Review(order_id=order.id, stage="val1", result=val1["result"], reviewer="系统", note=val1["summary"]))
    db.flush()

    if val1["result"] == "不通过":
        transition(order, "val1_failed", f"Val1 不通过：{val1['summary']}")
        db.commit()
        return {"order": _order_out(db, order), "val1": val1}
    if val1["result"] == "警告":
        transition(order, "val1_appeal", f"Val1 警告：{val1['summary']}（可接受风险申诉或修改模型）")
        db.commit()
        return {"order": _order_out(db, order), "val1": val1}

    transition(order, "slicing", "Val1 通过，进入耗材选择与参数设置（§4.1）")
    db.commit()
    return {"order": _order_out(db, order), "val1": val1}


def _do_slice(db: Session, order: Order, config: dict, note: str, confirm_required: bool = True) -> dict:
    transition(order, "slicing", note)
    material = _material_from_config(config, order.material_id)
    params = dict(order.params or {})
    if "preset" in params:
        presets = {p["id"]: p for p in config.get("presets", [])}
        preset = presets.get(params["preset"], {})
        merged = {**preset, **{k: v for k, v in params.items() if k != "preset"}}
        order.params = merged
    mv = db.get(ModelVersion, order.model_version_id) if order.model_version_id else None
    from ..core.config import settings as _st
    model_path = prepare_slice_file(order, mv, Path(_st.data_dir) / "slices")
    slice_result = run_slice(order.geometry, order.params, material, config, model_path)
    order.slice = slice_result
    val2auto = run_val2_auto(slice_result, order, order.params, material, config)
    order.val2auto = val2auto
    if confirm_required:
        # 用户预览确认后再提交 Val2（§6：提交切片 → 预览 → 返回调整/提交审核）
        transition(order, "slicing",
                   f"切片完成（预计 {round(slice_result['est_time_sec'] / 60)}min / {slice_result['est_weight_g']}g），"
                   f"等待预览确认（可返回调整或提交审核）")
        db.commit()
    else:
        transition(order, "val2_pending",
                   f"切片完成（预计 {round(slice_result['est_time_sec'] / 60)}min / {slice_result['est_weight_g']}g），"
                   f"Val2 自动检查{val2auto['result']}，等待负责人人工审核")
        db.commit()
    return {"order": _order_out(db, order), "val1": order.val1, "slice": slice_result, "val2auto": val2auto}


class SliceIn(BaseModel):
    material_id: str = "pla"
    color: str = "#E8602C"
    params: dict
    self_filament: bool = False


@router.post("/orders/{order_id}/slice")
def submit_slice(order_id: int, body: SliceIn, db: DbDep, user: UserDep):
    """耗材选择 + 参数设置 → 切片 → Val2 自动检查（§4.1：Val1 通过后）。
    返回切片结果与 G-code 预览数据（进阶）。"""
    order = get_order_or_403(db, order_id, user)
    if order.status not in ("slicing", "val2_failed", "rework"):
        raise HTTPException(status_code=409, detail="当前状态不能提交切片参数")
    order.material_id = body.material_id
    order.color = body.color
    order.params = body.params
    order.self_filament = body.self_filament
    config = get_activity_config(db, order.campaign)
    try:
        return _do_slice(db, order, config, "云端切片中（OrcaSlicer）")
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=f"切片失败：{e}")


@router.get("/orders/{order_id}/layer-preview")
def layer_preview(order_id: int, db: DbDep, user: UserDep, max_layers: int = 80):
    """逐层路径预览（§6.2/§7.3）：从切片产物 plate_1.gcode 解析每层挤出路径"""
    import zipfile
    order = get_order_or_403(db, order_id, user)
    pf = (order.slice or {}).get("project_file")
    if not pf or not os.path.exists(pf):
        raise HTTPException(status_code=404, detail="该需求尚未切片")
    with zipfile.ZipFile(pf) as z:
        if "Metadata/plate_1.gcode" not in z.namelist():
            raise HTTPException(status_code=404, detail="切片产物缺少 G-code")
        gcode = z.read("Metadata/plate_1.gcode").decode("utf-8", errors="replace")
    layers = parse_gcode_layers(gcode, max_layers=max_layers)
    return {"layers": layers, "count": len(layers), "layer_height": (order.params or {}).get("layer_height") or 0.2}


@router.post("/orders/{order_id}/confirm-slice")
def confirm_slice(order_id: int, db: DbDep, user: UserDep):
    """预览确认 → 提交 Val2 人工审核"""
    order = get_order_or_403(db, order_id, user)
    if order.status != "slicing":
        raise HTTPException(status_code=409, detail="当前状态不能提交审核")
    if not order.slice:
        raise HTTPException(status_code=409, detail="尚未切片")
    transition(order, "val2_pending", "切片预览确认，提交 Val2 人工审核")
    db.commit()
    return {"order": _order_out(db, order)}


@router.post("/orders/{order_id}/back-to-modeling")
def back_to_modeling(order_id: int, db: DbDep, user: UserDep):
    """预览不满意 → 返回摆放调整（重新走 Val1）"""
    order = get_order_or_403(db, order_id, user)
    if order.status != "slicing":
        raise HTTPException(status_code=409, detail="当前状态不能返回调整")
    transition(order, "modeling", "返回摆放调整（重新走 Val1）")
    db.commit()
    return {"order": _order_out(db, order)}


@router.get("/slicing/queue")
def slicing_queue(db: DbDep, user: UserDep):
    """云端切片队列状态（执行中/排队中/并发上限），供前端排队提示"""
    return slice_queue_stats()


# ---------- 申诉 / 重新提交 / 重切 ----------

class AppealIn(BaseModel):
    note: str = "接受风险，申请人工审核"


@router.post("/orders/{order_id}/appeal")
def appeal(order_id: int, body: AppealIn, db: DbDep, user: UserDep):
    order = get_order_or_403(db, order_id, user)
    if order.status != "val1_appeal":
        raise HTTPException(status_code=409, detail="当前状态不能申诉")
    order.appeal = {"note": body.note, "at": _now()}
    db.commit()
    return {"order": _order_out(db, order)}


@router.post("/orders/{order_id}/resubmit")
def resubmit(order_id: int, body: ResubmitIn, db: DbDep, user: UserDep):
    order = get_order_or_403(db, order_id, user)
    if order.status not in ("val1_appeal", "val1_failed"):
        raise HTTPException(status_code=409, detail="当前状态不能重新提交")
    # 新模型版本（§13.1：不覆盖历史版本）
    if order.model_id:
        version = ModelVersion(model_id=order.model_id, version=db.query(ModelVersion)
                               .filter_by(model_id=order.model_id).count() + 1,
                               file_path=db.get(ModelVersion, order.model_version_id).file_path if order.model_version_id else "",
                               stats=order.geometry or {}, checks={})
        db.add(version)
        db.flush()
        order.model_version_id = version.id
    order.placement = body.placement
    order.geometry = body.geometry
    order.material_id = body.material_id
    order.color = body.color
    order.params = body.params
    transition(order, "modeling", "已生成新模型版本，重新进入摆放与 Val1")
    db.commit()
    return {"order": _order_out(db, order)}


@router.post("/orders/{order_id}/reslice")
def reslice(order_id: int, body: ResliceIn, db: DbDep, user: UserDep):
    order = get_order_or_403(db, order_id, user)
    if order.status not in ("val2_failed", "rework"):
        raise HTTPException(status_code=409, detail="当前状态不能重新切片")
    order.params = body.params
    order.material_id = body.material_id
    order.color = body.color
    config = get_activity_config(db, order.campaign)
    try:
        return _do_slice(db, order, config, "调整参数后重新切片")
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=f"切片失败：{e}")


# ---------- 用户反馈 / 结清 ----------

class FeedbackIn(BaseModel):
    content: str


@router.post("/orders/{order_id}/feedback")
def feedback(order_id: int, body: FeedbackIn, db: DbDep, user: UserDep):
    order = get_order_or_403(db, order_id, user)
    order.feedback = {"content": body.content, "at": _now()}
    db.commit()
    return {"order": _order_out(db, order)}


@router.post("/orders/{order_id}/settle")
def settle(order_id: int, db: DbDep, user: UserDep):
    order = get_order_or_403(db, order_id, user)
    if order.status != "settlement":
        raise HTTPException(status_code=409, detail="该需求不在成本核算中")
    transition(order, "completed", "成本核算完成，计入活动账单")
    db.commit()
    return {"order": _order_out(db, order)}


def _now():
    from datetime import datetime
    return datetime.utcnow().isoformat(timespec="seconds")
