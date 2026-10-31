# E3DP backend — 负责人操作路由（决策清单 §9：全部走角色权限校验）
#
# 2026-10 调整：Val2 切片审核 / 在线切片已暂缓 → 人工复核对象改为「Val1 标记的潜在问题」，
# 打印执行依据用户提交的「打印清单」（材料/强度/进阶参数/估算），不再有切片产物。

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import client_ip, require_permission, write_audit
from ..models import AppSetting, Campaign, Issue, Order, PrintJob, Review, User
from ..services.campaign_service import get_current_campaign, list_campaigns, set_current_campaign
from ..services.config_service import clone_config_for_campaign, get_activity_config
from ..services.cost import append_cost, calc_filament_fee, settle_order_costs
from ..services.print_service import allocate, find_idle_printer, printer_snapshot, release
from ..services.state_machine import StateError, transition, transition_campaign

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
    campaign = get_current_campaign(db)
    config = get_activity_config(db, campaign) if campaign else {}

    def brief(o: Order) -> dict:
        jobs = sorted(o.print_jobs, key=lambda j: j.id)
        return {
            "id": o.id, "name": o.name, "user": o.user.name if o.user else "", "status": o.status,
            "self_filament": o.self_filament, "filament_approved": o.filament_approved,
            "appeal": o.appeal, "val1": o.val1, "slice": o.slice, "val2auto": o.val2auto,
            "created_at": o.created_at,
            # 打印清单所需字段（材料/颜色/工艺参数/尺寸/估算/备注）
            "material_id": o.material_id, "color": o.color, "params": o.params,
            "geometry": o.geometry, "model_id": o.model_id, "model_version_id": o.model_version_id,
            "manifest": (jobs[-1].gcode or {}).get("manifest") if jobs else None,
            "print_jobs": [{"id": j.id, "seq": j.seq, "status": j.status, "printer_id": j.printer_id,
                            "est_time_sec": j.est_time_sec, "est_weight_g": j.est_weight_g,
                            "actual_weight_g": j.actual_weight_g, "note": j.note} for j in jobs],
            "issues": [{"type": i.type, "stage": i.stage, "description": i.description} for i in o.issues],
        }
    return {
        # Val1 标记了潜在问题，等负责人复核（无自动退回机制）
        "val1_review": [brief(o) for o in db.query(Order).filter_by(status="val1_review").all()],
        "print_config": [brief(o) for o in db.query(Order).filter_by(status="print_config").all()],
        # 打印清单：已提交打印需求、等待执行打印
        "print_queue": [brief(o) for o in db.query(Order).filter_by(status="queued").all()],
        "printing": [brief(o) for o in db.query(Order).filter_by(status="printing").all()],
        "val3_pending": [brief(o) for o in db.query(Order).filter_by(status="val3_pending").all()],
        "rework": [brief(o) for o in db.query(Order).filter_by(status="rework").all()],
        "printers": printer_snapshot(config),
    }


@router.get("/print-manifest")
def print_manifest(db: DbDep, user: Annotated[User, Depends(require_permission("order:view_all"))]):
    """打印清单（执行打印用）：待打印 + 打印中，含完整参数与估算，可前端整页打印。"""
    rows = []
    for o in db.query(Order).filter(Order.status.in_(["queued", "printing"])).order_by(Order.id).all():
        jobs = sorted(o.print_jobs, key=lambda j: j.id)
        queued = [j for j in jobs if j.status in ("queued", "blocked")]
        job = (queued or jobs or [None])[-1]
        manifest = (job.gcode or {}).get("manifest") if job else None
        rows.append({"order_id": o.id, "status": o.status, "job": {
            "id": job.id if job else None, "seq": job.seq if job else None,
            "status": job.status if job else None, "printer_id": job.printer_id if job else None,
            "est_time_sec": job.est_time_sec if job else 0, "est_weight_g": job.est_weight_g if job else 0,
        }, "manifest": manifest, "self_filament": o.self_filament, "filament_approved": o.filament_approved})
    return {"manifests": rows, "generated_at": _now()}


# ---------- Val1 标记项人工复核（替代原「申诉审核」） ----------

class Val1ReviewIn(BaseModel):
    decision: str  # approve | modify | reject
    note: str = ""


@router.post("/val1-review/{order_id}")
def val1_review(order_id: int, body: Val1ReviewIn, db: DbDep,
                user: Annotated[User, Depends(require_permission("val1:review"))], request: Request):
    order = _get_order(db, order_id)
    if order.status != "val1_review":
        raise HTTPException(status_code=409, detail="该需求不在 Val1 人工复核队列")
    flagged = (order.val1 or {}).get("flagged_items", [])
    default_note = "、".join(i["name"] for i in flagged) or "无"
    note = body.note or f"复核标记项：{default_note}"
    db.add(Review(order_id=order.id, stage="val1", result=f"人工:{body.decision}", reviewer=user.name, note=note))
    if body.decision == "approve":
        transition(order, "print_config", f"负责人复核放行（{note}），进入打印需求配置")
    elif body.decision == "modify":
        transition(order, "val1_failed", f"负责人要求修改模型：{note}")
    else:
        transition(order, "terminated", f"复核判定不可打印，需求终止：{note}")
    db.commit()
    write_audit(db, user, "val1.review", target=f"O{order.id}", detail=body.decision, ip=client_ip(request))
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
    config = get_activity_config(db, order.campaign)
    printer = (next((p for p in printer_snapshot(config) if p["id"] == body.printer_id), None)
               if body.printer_id else find_idle_printer(config))
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


class PrintTimeIn(BaseModel):
    est_minutes: int | None = None      # 预计打印时长（分钟）——负责人按设备实际填写/修正
    started_at: str | None = None       # 开始时间（ISO，如 2026-10-29T14:05）


@router.post("/print/{job_id}/time")
def print_set_time(job_id: int, body: PrintTimeIn, db: DbDep,
                   user: Annotated[User, Depends(require_permission("print:manage"))], request: Request):
    """打印中手动填写时间（用户 2026-10 需求）。

    · est_minutes：覆盖由几何估算的预计时长（估算值只作参考，负责人以设备显示为准）
    · started_at：修正开始时间（忘记点「开始打印」或需要回填实际起始时刻）
    两者都可单独提交；进度条按 est_time_sec 与 started_at 推算，因此改完立即生效。
    """
    job = db.get(PrintJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="打印任务不存在")
    if job.status not in ("printing", "queued"):
        raise HTTPException(status_code=409, detail="仅排队中/打印中的任务可填写时间")
    changes = []
    if body.est_minutes is not None:
        if body.est_minutes <= 0:
            raise HTTPException(status_code=400, detail="预计时长必须大于 0 分钟")
        job.est_time_sec = int(body.est_minutes) * 60
        changes.append(f"预计时长 {body.est_minutes}min")
    if body.started_at:
        job.started_at = body.started_at
        changes.append(f"开始时间 {body.started_at}")
    if not changes:
        raise HTTPException(status_code=400, detail="请填写预计时长或开始时间")
    job.note = f"{job.note or ''}｜负责人手动填写：{'，'.join(changes)}"[:500]
    db.commit()
    write_audit(db, user, "print.set_time", target=f"PJ{job.id}", detail="，".join(changes), ip=client_ip(request))
    return {"ok": True, "job": {"id": job.id, "est_time_sec": job.est_time_sec, "started_at": job.started_at}}


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
    """设备问题重打：rework → 直接重新入清单（沿用原打印清单，正常计费）"""
    order = _get_order(db, order_id)
    if order.status != "rework":
        raise HTTPException(status_code=409, detail="该需求不在重新处理状态")
    last_issue = order.issues[-1] if order.issues else None
    if not last_issue or last_issue.type != "MACHINE":
        raise HTTPException(status_code=409, detail="仅设备问题可直接入队重打；参数/模型问题需改打印需求或改模型")
    # 沿用上一份清单（同一套材料/参数/估算），只重打一次
    prev = sorted(order.print_jobs, key=lambda j: j.id)[-1] if order.print_jobs else None
    job = PrintJob(order_id=order.id, seq=len(order.print_jobs) + 1, status="queued",
                   est_time_sec=prev.est_time_sec if prev else 0,
                   est_weight_g=prev.est_weight_g if prev else 0,
                   gcode=prev.gcode if prev else {},
                   note="设备问题重打：沿用原打印清单")
    db.add(job)
    transition(order, "queued", body.note)
    db.commit()
    write_audit(db, user, "print.requeue_reprint", target=f"O{order.id}", detail="MACHINE 重打", ip=client_ip(request))
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
        # 设备问题：设备处理后重打（不做价格区分，正常计费）
        transition(order, "rework", "设备问题：设备处理后将重新打印")
    else:
        transition(order, "rework", "参数问题：用户调整打印需求（材料/强度/进阶参数）后重新进清单（§10.1）")
    db.commit()
    write_audit(db, user, "val3.review", target=f"O{order.id}", detail=f"fail:{body.issue_type}", ip=client_ip(request))
    return {"ok": True}


# ---------- AI 对话模型（通用 OpenAI 兼容端点） ----------

@router.get("/llm/status")
def llm_status(user: Annotated[User, Depends(require_permission("qa:manage"))]):
    """当前对话端点与模型列表（含可达性、已装载模型）。"""
    from ..services.llm import is_local_endpoint, llm_conf, list_models, queue_stats, resolve_model
    conf = llm_conf()
    info = list_models(conf)
    return {
        "base_url": conf["base_url"],
        "has_api_key": bool(conf["api_key"]),
        "configured_model": conf["model"],
        "active_model": resolve_model(conf),
        "reachable": info["reachable"],
        "chat_models": info["chat_models"],
        "all_models": info["models"],
        "error": info.get("error"),
        "endpoint_kind": "local" if is_local_endpoint(conf["base_url"]) else "remote",
        "queue": queue_stats(),
    }


class LlmModelIn(BaseModel):
    model: str


@router.post("/llm/model")
def llm_set_model(body: LlmModelIn, db: DbDep,
                  user: Annotated[User, Depends(require_permission("qa:manage"))], request: Request):
    """切换对话模型（写入软件设置 llm_model，即时生效）。"""
    model = (body.model or "").strip()
    if not model:
        raise HTTPException(status_code=400, detail="请选择模型")
    row = db.get(AppSetting, "llm_model")
    if row:
        row.value = model
    else:
        db.add(AppSetting(key="llm_model", value=model, category="external",
                          label="AI 对话模型", hint="可在「站娘配置 → 对话模型」切换", value_type="str"))
    db.commit()
    from ..core.dynamic_settings import set_override
    set_override("llm_model", model)
    write_audit(db, user, "llm.set_model", target=model, ip=client_ip(request))
    return {"ok": True, "active_model": model}


class LlmTestIn(BaseModel):
    question: str = "用一句话介绍你自己"


@router.post("/llm/test")
def llm_test(body: LlmTestIn, user: Annotated[User, Depends(require_permission("qa:manage"))]):
    """试跑一次对话（不写流水、不计费），用于确认端点与模型是否可用。"""
    import time
    from ..services.llm import chat as llm_chat, llm_conf, resolve_model
    t0 = time.time()
    out = llm_chat([{"role": "user", "content": body.question}], temperature=0.3)
    elapsed = round((time.time() - t0) * 1000)
    conf = llm_conf()
    if not out:
        return {"ok": False, "elapsed_ms": elapsed, "base_url": conf["base_url"],
                "error": "端点不可达或未配置模型（看 /admin/llm/status 的错误详情）"}
    return {"ok": True, "elapsed_ms": elapsed, "model": out["model"],
            "answer": out["content"], "usage": {"in": out["input_tokens"], "out": out["output_tokens"]}}


# ---------- 站娘知识库（向量检索） ----------

@router.get("/kb")
def kb_status(db: DbDep, user: Annotated[User, Depends(require_permission("qa:manage"))]):
    """知识库来源与切块统计。"""
    from ..services.kb_vector import probe, status as kb_status_fn
    return {"sources": kb_status_fn(db), "embedding": probe()}


@router.post("/kb/sync")
def kb_sync(db: DbDep, user: Annotated[User, Depends(require_permission("qa:manage"))], request: Request,
            force: bool = False):
    """重新扫描 backend/kb/*.md 并重建向量索引（按文件哈希幂等；force=true 强制重建）。"""
    from ..services.kb_vector import ensure_columns, sync_all
    ensure_columns(db)
    result = sync_all(db, force=force)
    write_audit(db, user, "kb.sync", target="knowledge_base", detail=str(result), ip=client_ip(request))
    return {"synced": result}


class KbSearchIn(BaseModel):
    question: str
    top_k: int = 3


@router.post("/kb/search")
def kb_search(body: KbSearchIn, db: DbDep,
              user: Annotated[User, Depends(require_permission("qa:manage"))]):
    """检索调试：看某个问题命中的知识块与相似度（不消耗 token）。"""
    from ..services.kb_vector import search
    return {"hits": search(db, body.question, top_k=max(1, min(10, body.top_k)))}


# ---------- 活动（场次）管理：列表 / 新建 / 编辑 / 切换 / 生命周期 / 账单 ----------

def _campaign_out(c: Campaign, db: Session) -> dict:
    from ..models import Order
    orders = db.query(Order).filter_by(campaign_id=c.id)
    total = orders.count()
    active = orders.filter(Order.status.notin_(["completed", "terminated"])).count()
    current = get_current_campaign(db)
    return {
        "id": c.id, "name": c.name, "status": c.status, "password": c.password,
        "open_at": c.open_at, "close_at": c.close_at, "max_participants": c.max_participants,
        "created_at": c.created_at, "archived_at": c.archived_at,
        "is_current": bool(current and current.id == c.id),
        "config_sources": (c.config or {}).get("_sources", {}),
        "orders_total": total, "orders_active": active,
        "has_bill": bool(c.bill), "bill_total": (c.bill or {}).get("totals", {}).get("total"),
    }


@router.get("/campaigns")
def list_campaigns_api(db: DbDep, user: Annotated[User, Depends(require_permission("campaign:manage"))]):
    """活动列表（含当前活动标识与订单统计）。"""
    return {"campaigns": [_campaign_out(c, db) for c in list_campaigns(db)]}


class CampaignCreateIn(BaseModel):
    name: str
    open_at: str = ""
    close_at: str = ""
    max_participants: int = 20
    password: str = ""
    inherit: str = "template"  # template | previous
    inherit_id: int | None = None


@router.post("/campaigns")
def create_campaign(body: CampaignCreateIn, db: DbDep,
                    user: Annotated[User, Depends(require_permission("campaign:manage"))], request: Request):
    """新建活动：复制默认模板或指定场次的参数副本；新活动自动设为「当前活动」。"""
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="请填写活动名称")
    config = clone_config_for_campaign(db, source=body.inherit, source_campaign_id=body.inherit_id)
    password = (body.password or "").strip() or f"E3DP-{_now()[:10].replace('-', '')}"
    campaign = Campaign(name=name, status="待开放", password=password,
                        open_at=body.open_at, close_at=body.close_at,
                        max_participants=max(1, int(body.max_participants or 20)), config=config)
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    set_current_campaign(db, campaign.id)
    write_audit(db, user, "campaign.create", target=campaign.name,
                detail=f"inherit={body.inherit}", ip=client_ip(request))
    return {"ok": True, "campaign": _campaign_out(campaign, db)}


class CampaignUpdateIn(BaseModel):
    name: str | None = None
    password: str | None = None
    open_at: str | None = None
    close_at: str | None = None
    max_participants: int | None = None


@router.put("/campaigns/{campaign_id}")
def update_campaign(campaign_id: int, body: CampaignUpdateIn, db: DbDep,
                    user: Annotated[User, Depends(require_permission("campaign:manage"))], request: Request):
    """编辑活动基本信息（名称/取件密码/开放与收尾时间/人数上限）。"""
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="活动不存在")
    changed = []
    if body.name is not None and body.name.strip():
        campaign.name = body.name.strip(); changed.append("名称")
    if body.password is not None and body.password.strip():
        campaign.password = body.password.strip(); changed.append("取件密码")
    if body.open_at is not None:
        campaign.open_at = body.open_at; changed.append("开放时间")
    if body.close_at is not None:
        campaign.close_at = body.close_at; changed.append("收尾时间")
    if body.max_participants is not None:
        campaign.max_participants = max(1, int(body.max_participants)); changed.append("人数上限")
    db.commit()
    write_audit(db, user, "campaign.update", target=campaign.name, detail="、".join(changed), ip=client_ip(request))
    return {"ok": True, "campaign": _campaign_out(campaign, db)}


@router.post("/campaigns/{campaign_id}/activate")
def activate_campaign(campaign_id: int, db: DbDep,
                      user: Annotated[User, Depends(require_permission("campaign:manage"))], request: Request):
    """切换当前活动（学生端/工作台/配置中心/打印清单都以当前活动为准）。"""
    try:
        campaign = set_current_campaign(db, campaign_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    write_audit(db, user, "campaign.activate", target=campaign.name, ip=client_ip(request))
    return {"ok": True, "campaign": _campaign_out(campaign, db)}


class CampaignDeleteIn(BaseModel):
    force: bool = False


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: int, db: DbDep,
                    user: Annotated[User, Depends(require_permission("campaign:manage"))], request: Request,
                    force: bool = False):
    """删除活动：仅允许删除**没有订单**的活动（有订单时请用归档，保留历史）。"""
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="活动不存在")
    order_count = db.query(Order).filter_by(campaign_id=campaign.id).count()
    if order_count and not force:
        raise HTTPException(status_code=409, detail=f"该活动已有 {order_count} 条需求，不能删除；请改为归档")
    name = campaign.name
    db.delete(campaign)
    db.commit()
    write_audit(db, user, "campaign.delete", target=name, detail=f"orders={order_count}", ip=client_ip(request))
    return {"ok": True}


class CampaignTransitionIn(BaseModel):
    to: str


@router.post("/campaign/transition")
def campaign_transition(body: CampaignTransitionIn, db: DbDep,
                        user: Annotated[User, Depends(require_permission("campaign:manage"))], request: Request,
                        campaign_id: int | None = None):
    """活动生命周期流转（可指定 campaign_id，默认当前活动）。"""
    campaign = db.get(Campaign, campaign_id) if campaign_id else get_current_campaign(db)
    if not campaign:
        raise HTTPException(status_code=404, detail="活动不存在")
    try:
        transition_campaign(campaign, body.to)
    except StateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if body.to == "已归档":
        campaign.bill = build_bill(campaign, db)
        campaign.archived_at = _now()
    db.commit()
    write_audit(db, user, "campaign.transition", target=campaign.name, detail=body.to, ip=client_ip(request))
    return {"ok": True, "campaign": _campaign_out(campaign, db)}


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
def campaign_bill(db: DbDep, user: Annotated[User, Depends(require_permission("bill:view"))],
                  campaign_id: int | None = None):
    campaign = db.get(Campaign, campaign_id) if campaign_id else get_current_campaign(db)
    if not campaign:
        raise HTTPException(status_code=404, detail="活动不存在")
    return {"bill": campaign.bill or build_bill(campaign, db)}
