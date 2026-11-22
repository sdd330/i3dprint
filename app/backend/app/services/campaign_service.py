# E3DP backend — 活动（场次）管理服务
# 2026-10：新增「当前活动」指针（AppSetting.current_campaign_id）
#   之前所有地方都硬编码 `order_by(Campaign.id.desc()).first()`，只能"最新的一场"生效，
#   没法在管理界面切换场次；现在统一走 get_current_campaign(db)。

from __future__ import annotations

import hmac
import re
import secrets

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..core.security import check_login_rate, record_login_failure, write_audit
from ..models import AppSetting, Campaign

CURRENT_KEY = "current_campaign_id"

# 活动口令由学生手输（线下卡片/黑板/二维码），所以只取不易混淆的字符：
# 去掉 I / O / 0 / 1，剩下 32 个；8 位 ≈ 1.1e12 组合，配合登录限流足够抗在线爆破。
ACCESS_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ACCESS_LEN = 8

# 历史版本硬编码的弱默认口令（seed.py / admin.py 的日期串），启动时会被换成随机口令
_WEAK_ACCESS_PASSWORDS = {"E3DP-AUTUMN", "E3DPAUTUMN"}
_WEAK_DATE_PATTERN = re.compile(r"E3DP-?\d{8}")


def generate_access_password() -> str:
    """生成形如 `K7MQ-XT9P` 的活动口令；中间短横线只为人眼断句，校验时会被忽略。"""
    raw = "".join(secrets.choice(ACCESS_ALPHABET) for _ in range(ACCESS_LEN))
    return f"{raw[:4]}-{raw[4:]}"


def normalize_access_password(value: str | None) -> str:
    """输入容错：忽略大小写与空格/短横线/下划线（学生手输最常见的差异）。"""
    return re.sub(r"[\s\-_]+", "", value or "").upper()


def rotate_weak_access_passwords(db: Session) -> list[Campaign]:
    """把仍是历史默认口令的活动换成随机口令。

    只匹配已知的弱默认值，负责人自设的口令一概不碰。
    """
    rotated: list[Campaign] = []
    for camp in db.query(Campaign).all():
        current = (camp.password or "").strip()
        upper = current.upper()
        if upper not in _WEAK_ACCESS_PASSWORDS and not _WEAK_DATE_PATTERN.fullmatch(upper):
            continue
        camp.password = generate_access_password()
        rotated.append(camp)
        write_audit(db, None, "campaign.password_rotate", target=camp.name,
                    detail=f"检测到历史默认口令 {current}，已换成随机口令")
    if rotated:
        db.commit()
    return rotated


def list_campaigns(db: Session) -> list[Campaign]:
    return db.query(Campaign).order_by(Campaign.id.desc()).all()


def get_current_campaign(db: Session) -> Campaign | None:
    """当前生效的活动：优先取指针，其次最近一场；指针失效时自动纠正。"""
    row = db.get(AppSetting, CURRENT_KEY)
    if row and str(row.value or "").strip():
        try:
            camp = db.get(Campaign, int(row.value))
        except (TypeError, ValueError):
            camp = None
        if camp:
            return camp
    camp = db.query(Campaign).order_by(Campaign.id.desc()).first()
    if camp:
        _write_pointer(db, camp.id)
    return camp


def _write_pointer(db: Session, campaign_id: int) -> None:
    row = db.get(AppSetting, CURRENT_KEY)
    if row:
        row.value = str(campaign_id)
    else:
        db.add(AppSetting(key=CURRENT_KEY, value=str(campaign_id), category="misc",
                          label="当前活动 ID", hint="管理界面切换场次时更新；无需手动改",
                          value_type="str", restart_required=False))
    db.commit()


def set_current_campaign(db: Session, campaign_id: int) -> Campaign:
    camp = db.get(Campaign, campaign_id)
    if not camp:
        raise ValueError("活动不存在")
    _write_pointer(db, campaign_id)
    return camp


def verify_access_password(db: Session, provided: str, *, staff: bool, ip: str = "") -> None:
    """活动口令准入（公开部署下非负责人侧必须先过这一关）。

    口令线下分发，不在界面展示。两种情况放行并留审计，避免把学生端锁死：
      - 当前活动没有口令（管理员没设）
      - 当前活动已归档（活动结束，指针通常已切到新场次）
    """
    if staff:
        return
    camp = get_current_campaign(db)
    expected = (camp.password or "").strip() if camp else ""
    if not expected or camp.status == "已归档":
        write_audit(db, None, "auth.campaign_password_skip", target=str(camp.id) if camp else "",
                    detail=f"reason={'archived' if camp and camp.status == '已归档' else 'empty'}", ip=ip)
        return
    check_login_rate(ip)
    # 用 bytes 比对：负责人可能把口令设成中文，str 版 compare_digest 只支持 ASCII
    if not hmac.compare_digest(normalize_access_password(provided).encode(),
                               normalize_access_password(expected).encode()):
        record_login_failure(ip)
        write_audit(db, None, "auth.campaign_password_fail", target=str(camp.id),
                    detail="活动口令不正确", ip=ip)
        raise HTTPException(status_code=403, detail="活动口令不正确，请核对负责人线下发放的口令")
