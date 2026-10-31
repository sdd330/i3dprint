# E3DP backend — 业务实体（依据 context-gpt.md 实体建议 + 短期活动版设计）
# 短期活动版调整：无 TokenLedger（维护费并入费用）、新增 Campaign / 配置中心表

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base

# 两级状态机常量（设计文档 §12）
CAMPAIGN_STATUS = ["待开放", "开放中", "收尾中", "已归档"]

ORDER_STATUS = {
    "draft": "草稿",
    "modeling": "模型处理中",  # 含摆放/尺寸调整子阶段
    "val1_pending": "Val1审核中",
    # 2026-10：Val1 无退回机制——有潜在问题只做标记并转人工复核
    "val1_review": "Val1人工复核（已标记）",
    "val1_failed": "Val1人工判定需修改",
    "print_config": "待配置打印需求",  # 材料 / 强度 / 进阶参数 → 打印清单
    "queued": "待打印（已入清单）",
    "printing": "打印中",
    "val3_pending": "等待Val3验收",
    "val3_failed": "Val3未通过",
    "rework": "重新处理",
    "settlement": "成本核算中",
    "completed": "已完成",
    "terminated": "已终止",
    # —— 已暂缓（在线切片 + Val2 切片核验），仅为历史数据展示保留 ——
    "val1_appeal": "Val1警告/申诉中（旧流程）",
    "slicing": "切片中（旧流程）",
    "val2_pending": "Val2审核中（旧流程）",
    "val2_failed": "Val2未通过（旧流程）",
}

ISSUE_TYPES = {
    "PARAMETER": "参数问题",
    "MACHINE": "设备问题",
    "MODEL": "模型问题",
    "MACHINE_LIMIT": "设备能力上限",
    "CONTENT": "内容不合规",
    "OTHER": "其他",
}

PRINT_JOB_STATUS = ["queued", "printing", "done", "failed", "blocked"]


def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds")


# ---------- 权限与用户（决策清单 §9：RBAC 角色可配置、权限点解耦） ----------

class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)  # student / admin
    name: Mapped[str] = mapped_column(String(64))
    permissions: Mapped[list] = mapped_column(JSON, default=list)  # 权限点集合 ["order:create", ...]
    builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    users: Mapped[list["User"]] = relationship(back_populates="role")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # 学号/用户名
    name: Mapped[str] = mapped_column(String(64))
    grade: Mapped[str] = mapped_column(String(16), default="")
    contact: Mapped[str] = mapped_column(String(128), default="")
    hashed_password: Mapped[str] = mapped_column(String(256))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    role: Mapped[Role] = relationship(back_populates="users")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(String(32), default=now_iso)
    orders: Mapped[list["Order"]] = relationship(back_populates="user")


# ---------- 活动（设计文档 §3.2 / §12.1，配置副本 + 继承来源见 config_service） ----------

class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default="待开放")
    password: Mapped[str] = mapped_column(String(32))  # 活动密码（§16.1）
    open_at: Mapped[str] = mapped_column(String(32), default="")
    close_at: Mapped[str] = mapped_column(String(32), default="")
    max_participants: Mapped[int] = mapped_column(Integer, default=20)
    config: Mapped[dict] = mapped_column(JSON, default=dict)  # 活动参数副本（继承自模板/上一场）
    bill: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 活动账单（§12.4）
    archived_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), default=now_iso)
    orders: Mapped[list["Order"]] = relationship(back_populates="campaign")


# ---------- 模型（版本化，不覆盖，§13.1） ----------

class Model(Base):
    __tablename__ = "models"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(16), default="upload")  # preset / upload / ai
    created_at: Mapped[str] = mapped_column(String(32), default=now_iso)
    versions: Mapped[list["ModelVersion"]] = relationship(back_populates="model", cascade="all, delete-orphan")


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("models.id"))
    model: Mapped[Model] = relationship(back_populates="versions")
    version: Mapped[int] = mapped_column(Integer, default=1)
    file_path: Mapped[str] = mapped_column(String(256), default="")
    file_hash: Mapped[str] = mapped_column(String(64), default="")
    stats: Mapped[dict] = mapped_column(JSON, default=dict)  # 几何分析报告（体积/表面积/bbox等）
    checks: Mapped[dict] = mapped_column(JSON, default=dict)  # 封闭/流形/自交/壁厚/悬垂
    created_at: Mapped[str] = mapped_column(String(32), default=now_iso)


# ---------- 打印需求（订单，§3.4 / §12.2） ----------

class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    campaign: Mapped[Campaign] = relationship(back_populates="orders")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    user: Mapped["User"] = relationship(back_populates="orders")
    model_id: Mapped[int | None] = mapped_column(ForeignKey("models.id"), nullable=True)
    model_version_id: Mapped[int | None] = mapped_column(ForeignKey("model_versions.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(128), default="新打印需求")
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)

    # 摆放/耗材/参数（§4.3 / §4.4：摆放约束传递到切片）
    placement: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    geometry: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 前端分析报告 + 服务端校验结果
    material_id: Mapped[str] = mapped_column(String(16), default="pla")
    color: Mapped[str] = mapped_column(String(16), default="#E8602C")
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # 质量关卡快照（§5/§6/§7）
    val1: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    slice: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    val2auto: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # 申诉 / 自备耗材（§5.3 / §16.3）
    appeal: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    self_filament: Mapped[bool] = mapped_column(Boolean, default=False)
    filament_approved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    filament_note: Mapped[str] = mapped_column(Text, default="")

    # 费用（§11）+ 责任判定（§10）
    cost: Mapped[dict] = mapped_column(JSON, default=lambda: {"filament": 0, "maintenance": 0, "api": 0, "total": 0})
    reprint_rate: Mapped[dict] = mapped_column(JSON, default=dict)  # 设备问题半价重打
    feedback: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 用户反馈（§9.0）

    timeline: Mapped[list] = mapped_column(JSON, default=list)  # 状态时间轴
    created_at: Mapped[str] = mapped_column(String(32), default=now_iso)
    updated_at: Mapped[str] = mapped_column(String(32), default=now_iso)

    print_jobs: Mapped[list["PrintJob"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    reviews: Mapped[list["Review"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    issues: Mapped[list["Issue"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class PrintJob(Base):
    __tablename__ = "print_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    order: Mapped[Order] = relationship(back_populates="print_jobs")
    seq: Mapped[int] = mapped_column(Integer, default=1)  # 一个需求可对应多次打印任务（§3.5）
    printer_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    est_time_sec: Mapped[int] = mapped_column(Integer, default=0)
    est_weight_g: Mapped[float] = mapped_column(Float, default=0)
    actual_weight_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    gcode: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ended_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(String(32), default=now_iso)


class Review(Base):
    """审核记录（§13.3：Val1/Val2/Val3 人工与自动结果均记录）"""
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    order: Mapped[Order] = relationship(back_populates="reviews")
    stage: Mapped[str] = mapped_column(String(16))  # val1 / val2 / val3
    result: Mapped[str] = mapped_column(String(32))
    reviewer: Mapped[str] = mapped_column(String(64))
    note: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[str] = mapped_column(String(32), default=now_iso)


class Issue(Base):
    """问题记录：与订单状态分离（§12.3）"""
    __tablename__ = "issues"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    order: Mapped[Order] = relationship(back_populates="issues")
    stage: Mapped[str] = mapped_column(String(16))  # val2 / val3
    type: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="open")  # open / resolved
    created_at: Mapped[str] = mapped_column(String(32), default=now_iso)


# ---------- 费用流水（§13.5：append-only） ----------

class CostLedger(Base):
    __tablename__ = "cost_ledger"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    print_job_id: Mapped[int | None] = mapped_column(ForeignKey("print_jobs.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(16))  # filament / maintenance / api
    amount: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[str] = mapped_column(String(32), default=now_iso)


class ApiUsage(Base):
    """API 用量明细（决策清单 §5：按实际用量计费，不按次）"""
    __tablename__ = "api_usage"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # ai_modeling / qa
    service: Mapped[str] = mapped_column(String(16))  # tripo / deepseek
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    points: Mapped[float] = mapped_column(Float, default=0)  # Tripo 点数
    unit_price: Mapped[float] = mapped_column(Float, default=0)  # 元/单位
    amount: Mapped[float] = mapped_column(Float, default=0)  # 金额
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[str] = mapped_column(String(32), default=now_iso)


# ---------- 站娘问答工单（§15.2：GitHub Issue 式） ----------

class QaTicket(Base):
    __tablename__ = "qa_tickets"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(Text, default="")
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    author_name: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(16), default="open")  # open / answered / closed
    created_at: Mapped[str] = mapped_column(String(32), default=now_iso)
    comments: Mapped[list["QaTicketComment"]] = relationship(back_populates="ticket", cascade="all, delete-orphan")


class QaTicketComment(Base):
    __tablename__ = "qa_ticket_comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("qa_tickets.id"))
    ticket: Mapped[QaTicket] = relationship(back_populates="comments")
    author: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text)
    at: Mapped[str] = mapped_column(String(32), default=now_iso)


class KbSource(Base):
    """知识库文档来源（教材/手册等）：一份文档一条，按文件哈希判断是否需要重新切块。"""
    __tablename__ = "kb_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)     # 文件名
    path: Mapped[str] = mapped_column(String(256), default="")
    file_hash: Mapped[str] = mapped_column(String(64), default="")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    idf: Mapped[dict] = mapped_column(JSON, default=dict)            # 语料 IDF 表（供查询向量化复用）
    embedding_model: Mapped[str] = mapped_column(String(128), default="")  # 构建稠密索引用的模型（空=稀疏）
    updated_at: Mapped[str] = mapped_column(String(32), default=now_iso)


class KbChunk(Base):
    """知识库切块 + 稀疏向量（TF-IDF，L2 归一化；本地计算，不依赖外部 embedding API）"""
    __tablename__ = "kb_chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("kb_sources.id"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    heading: Mapped[str] = mapped_column(String(256), default="")    # 所属章节路径，如「第三章 材料 › 3.2 队内四种主力耗材」
    content: Mapped[str] = mapped_column(Text)
    vector: Mapped[dict] = mapped_column(JSON, default=dict)         # {token: weight}（TF-IDF 稀疏向量）
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)          # 稠密向量（正文，单位化）
    embedding_heading: Mapped[list | None] = mapped_column(JSON, nullable=True)  # 稠密向量（章节标题，单位化）
    char_count: Mapped[int] = mapped_column(Integer, default=0)


class QaKnowledge(Base):
    """站娘知识库条目（决策清单 §13：图形化配置，可绑 Spine 动画关键字）"""
    __tablename__ = "qa_knowledge"
    id: Mapped[int] = mapped_column(primary_key=True)
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    question: Mapped[str] = mapped_column(String(256), default="")
    answer: Mapped[str] = mapped_column(Text)
    step_context: Mapped[str] = mapped_column(String(64), default="")
    animation_key: Mapped[str] = mapped_column(String(64), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(String(32), default=now_iso)


# ---------- 配置中心（决策清单 §14：默认模板 + 活动副本继承 + 修改审计） ----------

class ConfigTemplate(Base):
    """默认活动模板（全局基线），新建活动时复制为活动参数副本"""
    __tablename__ = "config_templates"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), default="默认活动模板")
    is_default: Mapped[bool] = mapped_column(Boolean, default=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)  # 全量参数（费用/Val1阈值/档位/合规/站娘）
    updated_at: Mapped[str] = mapped_column(String(32), default=now_iso)


class ConfigAudit(Base):
    """配置修改审计（谁改了什么、何时改）"""
    __tablename__ = "config_audit"
    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[str] = mapped_column(String(16))  # template / campaign
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[str] = mapped_column(String(32))
    path: Mapped[str] = mapped_column(String(128))  # 参数路径，如 fee.materials.pla.price
    old_value: Mapped[str] = mapped_column(Text, default="")
    new_value: Mapped[str] = mapped_column(Text, default="")
    operator: Mapped[str] = mapped_column(String(64), default="")
    at: Mapped[str] = mapped_column(String(32), default=now_iso)


# ---------- 操作日志（§13.4） ----------

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    username: Mapped[str] = mapped_column(String(64), default="")
    action: Mapped[str] = mapped_column(String(64))  # login / order.create / val2.review ...
    target: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    at: Mapped[str] = mapped_column(String(32), default=now_iso)


class AppSetting(Base):
    """软件全局设置（环境变量图形化配置的落地点，跨活动不变；启动时从 DB 加载覆盖 env）"""
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(32), default="service")  # service/slicer/external/misc
    label: Mapped[str] = mapped_column(String(128), default="")
    hint: Mapped[str] = mapped_column(Text, default="")
    value_type: Mapped[str] = mapped_column(String(16), default="str")  # str/int/float/bool/secret
    restart_required: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[str] = mapped_column(String(32), default=now_iso)
