# E3DP backend — 打印需求（订单）主链路由（设计文档 §4-§11 / §12.2）
#
# 2026-10 调整：**在线切片与 Val2 切片核验暂缓**
#   用户 → 模型 → Val1（自动）─ 无问题 ─→ 打印需求配置（材料/强度/进阶参数）─→ 打印清单
#                            └ 有潜在问题 ─→ 标记 + 人工复核（不退回用户）
# 切片相关服务（services/slicing.py）保留未删，恢复时在此接回 /slice 接口即可。

from __future__ import annotations

import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.dynamic_settings import get_setting
from ..core.security import client_ip, get_current_user, write_audit
from ..models import Campaign
from ..models import Campaign, CostLedger, Model, ModelVersion, Order, PrintJob, Review, User
from ..services.campaign_service import get_current_campaign
from ..services.config_service import get_activity_config
from ..services.print_requirement import build_manifest, color_name, estimate, material_colors, merge_params
from ..services.state_machine import StateError, assert_campaign_open, transition
from ..services.val1 import run_val1
from .auth import _user_out  # noqa: F401  (保持与原路由一致的导入面)

router = APIRouter()

DbDep = Annotated[Session, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]


# 几何分析：上传阶段走进程内轻量解析（毫秒级）；生僻格式才退回子进程 trimesh（见 analysis_worker）
from ..services.analysis_worker import analyze_upload as _analyze_upload

# 可编辑模型的状态（草稿 / 摆放中 / 人工判定需修改 / 模型类返工）
EDITABLE_MODEL_STATUS = ("draft", "modeling", "val1_failed", "rework")


def get_order_or_403(db: Session, order_id: int, user: User) -> Order:
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="需求不存在")
    if user.role.code != "admin" and order.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问他人的需求")
    return order


def _order_out(db: Session, o: Order) -> dict:
    jobs = sorted(o.print_jobs, key=lambda j: j.id)
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
        # 打印清单（执行打印的负责人照此落地；无则在 val1 后还未提交需求）
        "manifest": (jobs[-1].gcode or {}).get("manifest") if jobs else None,
        "print_jobs": [_job_out(j) for j in jobs],
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
    model_id: int | None = None   # 历史模型（模型库中已有的模型）


class PlacementIn(BaseModel):
    placement: dict
    geometry: dict  # 前端分析报告（bbox/体积等）；服务端以 trimesh 真实分析为准兜底
    self_filament: bool = False  # 兼容旧参数；自备耗材在打印需求页确认


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
    campaign = get_current_campaign(db)
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
    transition(order, "draft", "创建打印需求")
    db.commit()
    write_audit(db, user, "order.create", target=f"O{order.id}", ip=client_ip(request))
    return {"order": _order_out(db, order)}


@router.get("/orders/{order_id}")
def get_order(order_id: int, db: DbDep, user: UserDep):
    order = get_order_or_403(db, order_id, user)
    return {"order": _order_out(db, order)}


@router.get("/models/{version_id}/file")
def model_file(version_id: int, db: DbDep, user: UserDep):
    """模型文件下载（摆放工作区三维预览 + 打印执行人下载模型用；归属校验）"""
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
    if order.status not in EDITABLE_MODEL_STATUS:
        raise HTTPException(status_code=409, detail="当前状态不能更换模型")
    if not body.model_id:
        raise HTTPException(status_code=400, detail="请先上传模型文件（STL / OBJ）")
    order.model_id = body.model_id
    mv = db.query(ModelVersion).filter_by(model_id=body.model_id).order_by(ModelVersion.version.desc()).first()
    order.model_version_id = mv.id if mv else None
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
    if order.status not in EDITABLE_MODEL_STATUS:
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
    stats = _analyze_upload(path, int(get_setting("analysis_timeout_sec", settings.analysis_timeout_sec)))
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
    """仅保存摆放结果（不触发 Val1）：工作区保存 → 下一步提交 Val1"""
    order = get_order_or_403(db, order_id, user)
    if order.status not in ("draft", "modeling", "val1_failed"):
        raise HTTPException(status_code=409, detail="当前状态不能保存摆放")
    order.placement = body.placement
    order.geometry = body.geometry
    db.commit()
    return {"order": _order_out(db, order)}


# ---------- 摆放提交 → Val1（自动；无退回，标记后转人工） ----------

@router.post("/orders/{order_id}/placement")
def submit_placement(order_id: int, body: PlacementIn, db: DbDep, user: UserDep):
    """摆放提交 → Val1（§5）。

    判定（无退回机制）：
      · 全部通过        → print_config（打印需求配置）
      · 有警告/不通过项 → val1_review（**标记** + 转负责人人工复核，订单不退回用户）
    """
    order = get_order_or_403(db, order_id, user)
    if order.status not in ("modeling", "val1_failed"):
        raise HTTPException(status_code=409, detail="当前状态不能提交摆放")
    if not order.model_version_id:
        raise HTTPException(status_code=400, detail="请先选择或上传模型")
    order.placement = body.placement
    order.geometry = body.geometry

    config = get_activity_config(db, order.campaign)
    transition(order, "val1_pending", "提交 Val1 自动审核")
    # 几何数据以服务端 trimesh 真实分析为准（模型版本 stats）；前端仅覆盖摆放后的 bbox（方向/尺寸约束，§4.4）
    mv = db.get(ModelVersion, order.model_version_id) if order.model_version_id else None
    stats = dict(mv.stats) if mv and mv.stats else dict(body.geometry or {})
    # 摆放缩放换算：壁厚/体积/表面积随 scale 线性/立方缩放（否则单位或缩放后的几何量失真，
    # 例：±0.5 坐标的模型放大 100 倍打印时，壁厚/体积必须按 scale 换算后再过 Val1）
    # scale 支持 [x,y,z] 三轴（前端手柄/单轴缩放）或单个数字（旧数据）
    raw_scale = (body.placement or {}).get("scale")
    if isinstance(raw_scale, (list, tuple)) and len(raw_scale) == 3:
        sx, sy, sz = (float(v or 1) for v in raw_scale)
    else:
        sx = sy = sz = float(raw_scale or 1)
    if (sx, sy, sz) != (1.0, 1.0, 1.0):
        if stats.get("bbox"):
            stats["bbox"] = [round(b * s, 2) for b, s in zip(stats["bbox"], (sx, sy, sz))]
        if stats.get("min_wall") is not None:
            stats["min_wall"] = round(stats["min_wall"] * min(sx, sy, sz), 2)
        if stats.get("volume_cm3"):
            stats["volume_cm3"] = round(stats["volume_cm3"] * sx * sy * sz, 2)
        if stats.get("surface_cm2"):
            stats["surface_cm2"] = round(stats["surface_cm2"] * (sx * sy + sy * sz + sz * sx) / 3, 1)
    if body.geometry and body.geometry.get("bbox"):
        stats["bbox"] = body.geometry["bbox"]
    val1 = run_val1(stats, config)  # 纯几何判定，不依赖耗材/参数
    flagged = [i for i in val1["items"] if i["level"] != "pass"]
    # 标记：哪个模型版本、哪些检查项有潜在问题（订单状态与问题分离，§12.3）
    val1["flagged"] = bool(flagged)
    val1["flagged_items"] = [{"id": i["id"], "name": i["name"], "level": i["level"], "message": i["message"]}
                             for i in flagged]
    order.val1 = val1
    db.add(Review(order_id=order.id, stage="val1", result=val1["result"], reviewer="系统", note=val1["summary"]))

    if not flagged:
        transition(order, "print_config", "Val1 通过（无潜在问题），进入打印需求配置")
        db.commit()
        return {"order": _order_out(db, order), "val1": val1, "next": "print_config"}

    names = "、".join(i["name"] for i in flagged[:4]) + ("…" if len(flagged) > 4 else "")
    transition(order, "val1_review",
               f"Val1 标记 {len(flagged)} 项潜在问题（{names}），转负责人人工复核（不退回用户）")
    db.commit()
    return {"order": _order_out(db, order), "val1": val1, "next": "val1_review"}


# ---------- 打印需求配置（材料 / 强度 / 进阶参数）→ 打印清单 ----------

class PrintRequirementIn(BaseModel):
    material_id: str = "pla"
    color: str = "#E8602C"
    strength: str = "standard"       # light / standard / strong / ultra
    advanced: dict | None = None     # 进阶手动覆盖（字段名同 OrcaSlicer）
    self_filament: bool = False      # 自备耗材（§16.3：先检验合格再打印）
    operator_note: str = ""          # 给执行打印人的备注


@router.post("/orders/{order_id}/print-requirement")
def submit_print_requirement(order_id: int, body: PrintRequirementIn, db: DbDep, user: UserDep):
    """Val1 通过（或人工放行）后：保存材料/强度/进阶参数 → 生成打印清单（PrintJob）。

    **不进行在线切片**：参数以结构化清单保存，执行打印的负责人据清单在切片器中落地。
    """
    order = get_order_or_403(db, order_id, user)
    if order.status not in ("print_config", "rework"):
        raise HTTPException(status_code=409, detail="当前状态不能提交打印需求")
    if order.status == "rework":
        last = order.issues[-1] if order.issues else None
        if last and last.type not in ("PARAMETER", "OTHER"):
            raise HTTPException(status_code=409,
                                detail="该问题需修改模型或由负责人安排重打，不能直接改打印需求")

    config = get_activity_config(db, order.campaign)
    material = _material_from_config(config, body.material_id)
    # 颜色必须属于该材料实际有货的颜色（配置中心按材料维护颜色清单）
    colors = material_colors(material)
    if colors:
        allowed = {c["hex"].upper() for c in colors}
        if body.color.upper() not in allowed:
            raise HTTPException(status_code=400,
                                detail=f"{material.get('name', body.material_id)} 没有该颜色，可选："
                                       + "、".join(f"{c['name']}({c['hex']})" for c in colors))
    params = merge_params(body.material_id, body.strength, body.advanced, config)
    if body.operator_note.strip():
        params["operator_note"] = body.operator_note.strip()[:500]

    order.material_id = body.material_id
    order.color = body.color
    order.params = params
    order.self_filament = body.self_filament

    est = estimate((order.val1 or {}).get("stats") or order.geometry or {}, material, params)
    manifest = build_manifest(order, material, params, est, config)

    seq = len(order.print_jobs) + 1
    job = PrintJob(order_id=order.id, seq=seq, status="queued",
                   est_time_sec=est["time_sec"], est_weight_g=est["weight_g"],
                   gcode={"source": "estimate", "manifest": manifest},
                   note=f"清单 #{seq}：{material['name']} · {params.get('strength_name')}强度 · "
                        f"{est['weight_g']}g（估算）/ {round(est['time_sec'] / 60)}min（估算）")
    db.add(job)
    blocked = False
    if order.self_filament and not order.filament_approved:
        job.status = "blocked"
        job.note += " · 自备耗材待检验（§16.3）"
        blocked = True
    transition(order, "queued",
               f"打印需求已提交（{material['name']} / {params.get('strength_name')}强度），"
               f"生成打印清单 #{seq}"
               + ("；自备耗材待检验合格后入队" if blocked else "，等待负责人执行打印"))
    db.commit()
    db.refresh(job)
    return {"order": _order_out(db, order), "job": _job_out(job), "manifest": manifest, "estimate": est}


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
