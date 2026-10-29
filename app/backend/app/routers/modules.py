"""独立模块路由：AI 建模（§14）+ 站娘问答（§15）+ 打印机状态。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import CurrentUser, StaffUser, require_permissions
from ..models.entities import User
from ..models.entities import Campaign, QaTicket
from ..services.ai import ai_generate
from ..services.config_service import get_activity_config
from ..services.qa import ask_qa

ai_router = APIRouter(prefix="/api/ai", tags=["ai"])


@ai_router.post("/generate")
def generate(payload: dict, user: User = Depends(require_permissions("ai:use")),
             db: Session = Depends(get_db)):
    """AI 建模：描述/尺寸 → 生成模型 + 就地体检（§14.1/§14.2）。按 Tripo 用量计费（§14.3）。"""
    campaign = db.query(Campaign).order_by(Campaign.id.desc()).first()
    cfg = get_activity_config(db, campaign) if campaign else {}
    result = ai_generate(db, payload.get("description", ""), payload.get("sizeCm", 8), cfg)
    if result.get("error"):
        raise HTTPException(502, result["error"])
    return result


qa_router = APIRouter(prefix="/api/qa", tags=["qa"])


@qa_router.post("/ask")
def ask(payload: dict, user: User = Depends(require_permissions("qa:ask")),
        db: Session = Depends(get_db)):
    """站娘问答：知识库命中不产生 API 费用；未命中走 DeepSeek，按 token 计费（§11.3）。"""
    campaign = db.query(Campaign).order_by(Campaign.id.desc()).first()
    cfg = get_activity_config(db, campaign) if campaign else {}
    result = ask_qa(db, payload.get("question", ""), payload.get("step", ""), cfg)
    return result


@qa_router.get("/tickets")
def list_tickets(user: CurrentUser, db: Session = Depends(get_db)):
    is_staff = user.role and user.role.name == "admin"
    q = db.query(QaTicket)
    if not is_staff:
        q = q.filter_by(author_id=user.id)
    return {"tickets": [{"id": t.id, "title": t.title, "content": t.content, "authorId": t.author_id,
                         "status": t.status, "comments": t.comments,
                         "createdAt": t.created_at.isoformat()} for t in q.order_by(QaTicket.id.desc()).all()]}


@qa_router.post("/tickets")
def create_ticket(payload: dict, user: CurrentUser, db: Session = Depends(get_db)):
    t = QaTicket(title=payload.get("title", ""), content=payload.get("content", ""), author_id=user.id)
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"ticket": {"id": t.id}}


@qa_router.post("/tickets/{tid}/comments")
def add_comment(tid: int, payload: dict, user: CurrentUser, db: Session = Depends(get_db)):
    t = db.get(QaTicket, tid)
    if not t:
        raise HTTPException(404, "工单不存在")
    comments = list(t.comments or [])
    from datetime import datetime, timezone
    comments.append({"author": user.name, "content": payload.get("content", ""),
                     "at": datetime.now(timezone.utc).isoformat()})
    t.comments = comments
    if user.role and user.role.name == "admin":
        t.status = "answered"
    db.commit()
    return {"ok": True}


@qa_router.post("/tickets/{tid}/status")
def set_ticket_status(tid: int, payload: dict, user: StaffUser, db: Session = Depends(get_db)):
    t = db.get(QaTicket, tid)
    if not t:
        raise HTTPException(404, "工单不存在")
    if payload.get("status") not in ("open", "answered", "closed"):
        raise HTTPException(400, "状态非法")
    t.status = payload["status"]
    db.commit()
    return {"ok": True}


printer_router = APIRouter(prefix="/api", tags=["printers"])


@printer_router.get("/printers")
def list_printers(user: User = Depends(require_permissions("printer:read")),
                  db: Session = Depends(get_db)):
    """设备清单来自活动配置（配置中心可增删）；忙闲状态取自运行时。"""
    from ..services.print_service import printer_snapshot
    campaign = db.query(Campaign).order_by(Campaign.id.desc()).first()
    cfg = get_activity_config(db, campaign) if campaign else {}
    return {"printers": printer_snapshot(cfg)}
