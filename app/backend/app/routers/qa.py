# E3DP backend — 站娘问答路由（§15.2：问答 + GitHub Issue 式工单）

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_current_user
from ..models import Campaign, QaKnowledge, QaTicket, User
from ..services.config_service import get_activity_config
from ..services.cost import append_api_usage
from ..services.qa_service import ask

router = APIRouter()

DbDep = Annotated[Session, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]


class AskIn(BaseModel):
    question: str
    step: str = ""


@router.post("/ask")
def qa_ask(body: AskIn, db: DbDep, user: UserDep):
    campaign = db.query(Campaign).order_by(Campaign.id.desc()).first()
    config = get_activity_config(db, campaign) if campaign else {}
    result = ask(db, user, body.question, body.step, config)
    if result.get("usage"):
        u = result["usage"]
        append_api_usage(db, kind="qa", service="deepseek", user_id=user.id,
                         input_tokens=u["input_tokens"], output_tokens=u["output_tokens"],
                         unit_price=config.get("fee", {}).get("api", {}).get("deepseek_input_per_mtok", 0),
                         meta={"step": body.step})
    return result


# ---------- 工单（GitHub Issue 式：发帖 + 状态 + 评论） ----------

class TicketIn(BaseModel):
    title: str
    content: str = ""


@router.get("/tickets")
def list_tickets(db: DbDep, user: UserDep):
    q = db.query(QaTicket)
    if user.role.code != "admin":
        q = q.filter_by(author_id=user.id)
    tickets = q.order_by(QaTicket.id.desc()).all()
    return {"tickets": [_t_out(t) for t in tickets]}


@router.post("/tickets")
def create_ticket(body: TicketIn, db: DbDep, user: UserDep):
    t = QaTicket(title=body.title, content=body.content, author_id=user.id, author_name=user.name)
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"ticket": _t_out(t)}


class CommentIn(BaseModel):
    content: str


@router.post("/tickets/{ticket_id}/comments")
def add_comment(ticket_id: int, body: CommentIn, db: DbDep, user: UserDep):
    t = db.get(QaTicket, ticket_id)
    if not t:
        raise HTTPException(status_code=404, detail="工单不存在")
    from ..models import QaTicketComment
    db.add(QaTicketComment(ticket_id=t.id, author=user.name, content=body.content))
    if user.role.code == "admin":
        t.status = "answered"
    db.commit()
    return {"ticket": _t_out(db.get(QaTicket, ticket_id))}


class StatusIn(BaseModel):
    status: str  # open / answered / closed


@router.post("/tickets/{ticket_id}/status")
def set_status(ticket_id: int, body: StatusIn, db: DbDep,
               user: Annotated[User, Depends(_admin)]):
    t = db.get(QaTicket, ticket_id)
    if not t:
        raise HTTPException(status_code=404, detail="工单不存在")
    t.status = body.status
    db.commit()
    return {"ticket": _t_out(t)}


def _admin(user: UserDep) -> User:
    if user.role.code != "admin":
        raise HTTPException(status_code=403, detail="仅负责人可操作")
    return user


def _t_out(t: QaTicket) -> dict:
    return {
        "id": t.id, "title": t.title, "content": t.content, "author_name": t.author_name,
        "status": t.status, "created_at": t.created_at,
        "comments": [{"author": c.author, "content": c.content, "at": c.at} for c in t.comments],
    }


# ---------- 知识库配置（决策清单 §13.1：图形化配置） ----------

class KnowledgeIn(BaseModel):
    keywords: list[str]
    question: str = ""
    answer: str
    step_context: str = ""
    animation_key: str = ""
    enabled: bool = True


@router.get("/knowledge")
def list_knowledge(db: DbDep, user: UserDep):
    return {"items": [{"id": k.id, "keywords": k.keywords, "question": k.question, "answer": k.answer,
                       "step_context": k.step_context, "animation_key": k.animation_key, "enabled": k.enabled}
                      for k in db.query(QaKnowledge).order_by(QaKnowledge.id).all()]}


@router.post("/knowledge")
def create_knowledge(body: KnowledgeIn, db: DbDep, user: Annotated[User, Depends(_admin)]):
    k = QaKnowledge(**body.model_dump())
    db.add(k)
    db.commit()
    db.refresh(k)
    return {"ok": True, "id": k.id}


@router.put("/knowledge/{item_id}")
def update_knowledge(item_id: int, body: KnowledgeIn, db: DbDep, user: Annotated[User, Depends(_admin)]):
    k = db.get(QaKnowledge, item_id)
    if not k:
        raise HTTPException(status_code=404, detail="条目不存在")
    for f, v in body.model_dump().items():
        setattr(k, f, v)
    db.commit()
    return {"ok": True}


@router.delete("/knowledge/{item_id}")
def delete_knowledge(item_id: int, db: DbDep, user: Annotated[User, Depends(_admin)]):
    k = db.get(QaKnowledge, item_id)
    if not k:
        raise HTTPException(status_code=404, detail="条目不存在")
    db.delete(k)
    db.commit()
    return {"ok": True}
