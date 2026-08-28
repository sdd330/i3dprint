# E3DP backend — 负责人操作路由（决策清单 §9：全部走角色权限校验）

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import client_ip, require_permission, write_audit
from ..models import Campaign, Issue, ModelVersion, Order, PrintJob, Review, User
from ..services.config_service import clone_config_for_campaign, get_activity_config
from ..services.cost import append_cost, calc_filament_fee, settle_order_costs
from ..services.print_service import PRINTERS, allocate, find_idle_printer, release
from ..services.state_machine import StateError, transition, transition_campaign
from ..services.val1 import run_val1
from ..services.slicing import prepare_slice_file, run_slice, run_val2_auto

router = APIRouter(prefix="/admin")

DbDep = Annotated[Session, Depends(get_db)]
AdminDep = Annotated[User, Depends(require_permission("campaign:manage"))]


def _now():
    return datetime.utcnow().isoformat(timespec="seconds")


def _get_order(db: Session, order_id: int) -> Order:
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="需求不存在")
    return order


# ---------- 审核队列汇总 ----------

@router.get("/queues")
def queues(db: DbDep, user: Annotated[User, Depends(require_permission("order:view_all"))]):
    def brief(o: Order) -> dict:
        return {
            "id": o.id, "name": o.name, "user": o.user.name if o.user else "", "status": o.status,
            "self_filament": o.self_filament, "appeal": o.appeal, "val1": o.val1,
            "slice": o.slice, "val2auto": o.val2auto, "created_at": o.created_at,
            "print_jobs": [{"id": j.id, "seq": j.seq, "status": j.status, "printer_id": j.printer_id,
                            "est_time_sec": j.est_time_sec, "note": j.note} for j in o.print_jobs],
            "issues": [{"type": i.type, "stage": i.stage} for i in o.issues],
        }
    return {
        "val1_appeal": [brief(o) for o in db.query(Order).filter_by(status="val1_appeal").all()],
        "val2_pending": [brief(o) for o in db.query(Order).filter_by(status="val2_pending").all()],
        "val3_pending": [brief(o) for o in db.query(Order).filter_by(status="val3_pending").all()],
        "print_queue": [brief(o) for o in db.query(Order).filter_by(status="queued").all()],
        "printing": [brief(o) for o in db.query(Order).filter_by(status="printing").all()],
        "rework": [brief(o) for o in db.query(Order).filter_by(status="rework").all()],
        "printers": PRINTERS,
    }


# ---------- Val1 申诉人工审核（§5.3） ----------

class Val1AppealIn(BaseModel):
    decision: str  # approve | modify | reject
    note: str = ""


@router.post("/val1-appeal/{order_id}")
def val1_appeal_review(order_id: int, body: Val1AppealIn, db: DbDep,
                       user: Annotated[User, Depends(require_permission("val1:review"))], request: Request):
    order = _get_order(db, order_id)
    if order.status != "val1_appeal":
        raise HTTPException(status_code=409, detail="该需求不在申诉审核队列")
    db.add(Review(order_id=order.id, stage="val1", result=f"人工:{body.decision}", reviewer=user.name, note=body.note))
    if body.decision == "approve":
        config = get_activity_config(db, order.campaign)
        transition(order, "slicing", "负责人同意申诉，进入切片")
        db.commit()
        _do_slice(db, order, config)
    elif body.decision == "modify":
        transition(order, "val1_failed", "负责人要求修改模型")
        db.commit()
    else:
        transition(order, "val1_failed", "申诉被驳回，判定不通过")
        db.commit()
    write_audit(db, user, "val1.appeal_review", target=f"O{order.id}", detail=body.decision, ip=client_ip(request))
    return {"ok": True}


def _do_slice(db: Session, order: Order, config: dict):
    material = next((m for m in config.get("fee", {}).get("materials", []) if m["id"] == order.material_id), {})
    mv = db.get(ModelVersion, order.model_version_id) if order.model_version_id else None
    from ..core.config import settings as _st
    from pathlib import Path as _P
    model_path = prepare_slice_file(order, mv, _P(_st.data_dir) / "slices")
    slice_result = run_slice(order.geometry, order.params, material, config, model_path)
    order.slice = slice_result
    val2auto = run_val2_auto(slice_result, order, order.params, material, config)
    order.val2auto = val2auto
    transition(order, "val2_pending", "切片完成，提交 Val2 人工审核")
    db.commit()


# ---------- Val2 人工审核 + 内容合规（§7.3/§7.4/§7.6） ----------

class Val2In(BaseModel):
    decision: str  # pass | reject
    issue_type: str = "PARAMETER"  # PARAMETER / MODEL / SLICING / CONTENT
    note: str = ""


@router.post("/val2/{order_id}")
def val2_review(order_id: int, body: Val2In, db: DbDep,
                user: Annotated[User, Depends(require_permission("val2:review"))], request: Request):
    order = _get_order(db, order_id)
    if order.status != "val2_pending":
        raise HTTPException(status_code=409, detail="该需求不在 Val2 审核队列")
    if body.decision == "pass":
        db.add(Review(order_id=order.id, stage="val2", result="通过", reviewer=user.name,
                      note=body.note or "人工切片审核 + 内容合规审核通过"))
        transition(order, "queued", "Val2 通过：生成打印任务，加入打印队列")
        db.commit()
        job = PrintJob(order_id=order.id, seq=len(order.print_jobs) + 1, status="queued",
                       est_time_sec=order.slice["est_time_sec"] if order.slice else 0,
                       est_weight_g=order.slice["est_weight_g"] if order.slice else 0,
                       gcode=order.slice["gcode"] if order.slice else {},
                       note="等待空闲打印机")
        db.add(job)
        db.commit()
        db.refresh(job)
        if order.self_filament and not order.filament_approved:
            # 自备耗材需先检验合格才可打印（§16.3）
            job.status = "blocked"
            job.note = "自备耗材待检验（§16.3），检验合格后自动入队"
            db.commit()
        write_audit(db, user, "val2.review", target=f"O{order.id}", detail="pass", ip=client_ip(request))
        return {"ok": True, "job": job.id}
    # 驳回
    db.add(Issue(order_id=order.id, stage="val2", type=body.issue_type, description=body.note))
    db.add(Review(order_id=order.id, stage="val2", result=f"不通过({body.issue_type})", reviewer=user.name, note=body.note))
    if body.issue_type == "CONTENT":
        transition(order, "terminated", f"内容不合规，需求终止：{body.note}")
    elif body.issue_type == "MODEL":
        transition(order, "val2_failed", "Val2 驳回：模型问题，需修改模型生成新版本并重走 Val1")
    else:
        transition(order, "val2_failed", f"Val2 驳回（{body.issue_type}）：{body.note}，调整后重新切片")
    db.commit()
    write_audit(db, user, "val2.review", target=f"O{order.id}", detail=f"reject:{body.issue_type}", ip=client_ip(request))
    return {"ok": True}


# ---------- 自备耗材检验（§16.3） ----------

class FilamentIn(BaseModel):
    approved: bool
    note: str = ""


@router.post("/orders/{order_id}/filament")
def filament_check(order_id: int, body: FilamentIn, db: DbDep,
                   user: Annotated[User, Depends(require_permission("filament:review"))]):
    order = _get_order(db, order_id)
    order.filament_approved = body.approved
    order.filament_note = body.note
    if body.approved:
        for job in order.print_jobs:
            if job.status == "blocked":
                job.status = "queued"
                job.note = "自备耗材检验合格，已入队"
    db.commit()
    write_audit(db, user, "filament.review", target=f"O{order.id}", detail=str(body.approved))
    return {"ok": True}


# ---------- 打印执行（§8 / §16.4） ----------

class PrintStartIn(BaseModel):
    printer_id: str | None = None


@router.post("/print/{job_id}/start")
def print_start(job_id: int, body: PrintStartIn, db: DbDep,
                user: Annotated[User, Depends(require_permission("print:manage"))], request: Request):
    job = db.get(PrintJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="打印任务不存在")
    order = db.get(Order, job.order_id)
    if job.status != "queued":
        raise HTTPException(status_code=409, detail="打印任务不在队列中")
    if order.self_filament and not order.filament_approved:
        raise HTTPException(status_code=409, detail="自备耗材未检验合格（§16.3）")
    printer = next((p for p in PRINTERS if p["id"] == body.printer_id), None) if body.printer_id else find_idle_printer()
    if not printer or printer["status"] != "idle":
        raise HTTPException(status_code=409, detail="没有空闲打印机")
    allocate(job, printer)
    job.status = "printing"
    transition(order, "printing", f"{printer['name']} 开始打印（预计 {round(job.est_time_sec / 60)}min）")
    db.commit()
    write_audit(db, user, "print.start", target=f"PJ{job.id}", ip=client_ip(request))
    return {"ok": True, "job_id": job.id, "printer": printer["name"]}


@router.post("/print/{job_id}/complete")
def print_complete(job_id: int, db: DbDep,
                   user: Annotated[User, Depends(require_permission("print:manage"))], request: Request):
    job = db.get(PrintJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="打印任务不存在")
    if job.status != "printing":
        raise HTTPException(status_code=409, detail="任务不在打印中")
    order = db.get(Order, job.order_id)
    import random
    job.status = "done"
    job.actual_weight_g = round(job.est_weight_g * (0.95 + random.random() * 0.1), 1)
    job.ended_at = _now()
    release(job.printer_id)
    transition(order, "val3_pending", f"打印完成（实际耗材 {job.actual_weight_g}g），等待实物验收")
    db.commit()
    write_audit(db, user, "print.complete", target=f"PJ{job.id}", ip=client_ip(request))
    return {"ok": True}


class PrintFailIn(BaseModel):
    note: str = "打印中途失败"


@router.post("/print/{job_id}/fail")
def print_fail(job_id: int, body: PrintFailIn, db: DbDep,
               user: Annotated[User, Depends(require_permission("print:manage"))], request: Request):
    job = db.get(PrintJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="打印任务不存在")
    order = db.get(Order, job.order_id)
    if job.status == "printing":
        release(job.printer_id)
    job.status = "queued"
    job.note = f"打印异常：{body.note}，重新排队（§16.4）"
    transition(order, "queued", f"打印异常，重新进入打印队列：{body.note}")
    db.commit()
    write_audit(db, user, "print.fail_requeue", target=f"PJ{job.id}", detail=body.note, ip=client_ip(request))
    return {"ok": True}


class RequeueIn(BaseModel):
    note: str = "设备已处理，安排重打（§10.2）"


@router.post("/orders/{order_id}/requeue")
def requeue(order_id: int, body: RequeueIn, db: DbDep,
            user: Annotated[User, Depends(require_permission("print:manage"))], request: Request):
    """设备问题重打：rework → 直接入队（不需重切），新 PrintJob 按半价计费（§10.2）"""
    order = _get_order(db, order_id)
    if order.status != "rework":
        raise HTTPException(status_code=409, detail="该需求不在重新处理状态")
    last_issue = order.issues[-1] if order.issues else None
    if not last_issue or last_issue.type != "MACHINE":
        raise HTTPException(status_code=409, detail="仅设备问题可直接入队重打；参数/模型问题需重切或改模型")
    job = PrintJob(order_id=order.id, seq=len(order.print_jobs) + 1, status="queued",
                   est_time_sec=order.slice["est_time_sec"] if order.slice else 0,
                   est_weight_g=order.slice["est_weight_g"] if order.slice else 0,
                   gcode=order.slice["gcode"] if order.slice else {},
                   note="设备问题半价重打（§10.2）")
    db.add(job)
    transition(order, "queued", body.note)
    db.commit()
    write_audit(db, user, "print.requeue_reprint", target=f"O{order.id}", detail="MACHINE 半价重打", ip=client_ip(request))
    return {"ok": True, "job_id": job.id}


# ---------- Val3 实物验收 + 责任判定（§9 / §10） ----------

class Val3In(BaseModel):
    decision: str  # pass | fail
    issue_type: str = "PARAMETER"
    note: str = ""


@router.post("/val3/{order_id}")
def val3_review(order_id: int, body: Val3In, db: DbDep,
                user: Annotated[User, Depends(require_permission("val3:review"))], request: Request):
    order = _get_order(db, order_id)
    if order.status != "val3_pending":
        raise HTTPException(status_code=409, detail="该需求不在 Val3 验收队列")
    if body.decision == "pass":
        db.add(Review(order_id=order.id, stage="val3", result="通过", reviewer=user.name, note=body.note))
        config = get_activity_config(db, order.campaign)
        settle_order_costs(db, order, config)  # §11 成本核算
        transition(order, "settlement", "Val3 验收通过，进入成本核算")
        db.commit()
        write_audit(db, user, "val3.review", target=f"O{order.id}", detail="pass", ip=client_ip(request))
        return {"ok": True}
    # 不通过：问题责任判定（§9.3 / §10）
    db.add(Issue(order_id=order.id, stage="val3", type=body.issue_type, description=body.note))
    db.add(Review(order_id=order.id, stage="val3", result=f"不通过({body.issue_type})", reviewer=user.name, note=body.note))
    if body.issue_type == "MACHINE_LIMIT":
        transition(order, "terminated", "设备能力上限：当前设备无法满足要求，需求终止（§10.4）")
    elif body.issue_type == "MODEL":
        transition(order, "rework", "模型问题：需修改模型生成新版本，重走 Val1（§10.3）")
    elif body.issue_type == "MACHINE":
        # 设备问题：半价重打（§10.2）
        seq = len(order.print_jobs) + 1
        order.reprint_rate = {**dict(order.reprint_rate or {}), str(seq): 0.5}
        transition(order, "rework", "设备问题：设备处理后半价重打（§10.2）")
    else:
        transition(order, "rework", "参数问题：调整参数后重新切片、打印（§10.1）")
    db.commit()
    write_audit(db, user, "val3.review", target=f"O{order.id}", detail=f"fail:{body.issue_type}", ip=client_ip(request))
    return {"ok": True}


# ---------- 活动生命周期与账单（§12.1 / §12.4） ----------

class CampaignTransitionIn(BaseModel):
    to: str


@router.post("/campaign/transition")
def campaign_transition(body: CampaignTransitionIn, db: DbDep,
                        user: Annotated[User, Depends(require_permission("campaign:manage"))], request: Request):
    campaign = db.query(Campaign).order_by(Campaign.id.desc()).first()
    try:
        transition_campaign(campaign, body.to)
    except StateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if body.to == "已归档":
        campaign.bill = build_bill(campaign, db)
        campaign.archived_at = _now()
    db.commit()
    write_audit(db, user, "campaign.transition", target=campaign.name, detail=body.to, ip=client_ip(request))
    return {"ok": True, "campaign": {"id": campaign.id, "status": campaign.status, "bill": campaign.bill}}


class CampaignCreateIn(BaseModel):
    name: str
    open_at: str = ""
    close_at: str = ""
    inherit: str = "template"  # template | previous
    inherit_id: int | None = None


@router.post("/campaigns")
def create_campaign(body: CampaignCreateIn, db: DbDep,
                    user: Annotated[User, Depends(require_permission("campaign:manage"))], request: Request):
    config = clone_config_for_campaign(db, source=body.inherit, source_campaign_id=body.inherit_id)
    campaign = Campaign(name=body.name, status="待开放", password=f"E3DP-{_now()[:10].replace('-', '')}",
                        open_at=body.open_at, close_at=body.close_at, config=config)
    db.add(campaign)
    db.commit()
    write_audit(db, user, "campaign.create", target=campaign.name, detail=f"inherit={body.inherit}", ip=client_ip(request))
    return {"ok": True, "campaign": {"id": campaign.id, "name": campaign.name, "status": campaign.status}}


def build_bill(campaign: Campaign, db: Session) -> dict:
    rows = []
    for o in db.query(Order).filter_by(campaign_id=campaign.id).all():
        if o.status in ("completed", "terminated"):
            rows.append({
                "order_id": o.id, "name": o.name, "user": o.user.name if o.user else "",
                "status": o.status, **dict(o.cost or {}),
            })
    totals = {"filament": 0, "maintenance": 0, "api": 0, "total": 0}
    for r in rows:
        for k in totals:
            totals[k] = round(totals[k] + r.get(k, 0), 2)
    return {"campaign_id": campaign.id, "generated_at": _now(), "rows": rows, "totals": totals}


@router.get("/campaign/bill")
def campaign_bill(db: DbDep, user: Annotated[User, Depends(require_permission("bill:view"))]):
    campaign = db.query(Campaign).order_by(Campaign.id.desc()).first()
    return {"bill": campaign.bill or build_bill(campaign, db)}
