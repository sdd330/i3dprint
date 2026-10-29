# E3DP backend — 费用核算（设计文档 §11 / 决策清单 §5）
# 总成本 = 耗材费 + 维护费 + Σ API服务费（按实际用量）
# 耗材费 = 材料成本价 × 模型重量 × 材料系数 + 换料补偿

from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import ApiUsage, CostLedger, Order

REPRINT_KINDS = {"PARAMETER": "参数问题重打", "MACHINE": "设备问题重打", "MODEL": "模型问题重打", "OTHER": "其他"}


def calc_filament_fee(material: dict, weight_g: float, change_fee: float, color_changes: int = 0) -> dict:
    base = material.get("price_per_g", 0) * weight_g * material.get("coeff", 1.0)
    change = change_fee * color_changes if color_changes > 1 else 0.0
    return {"base": round(base, 2), "change": round(change, 2), "total": round(base + change, 2)}


def calc_maintenance(weight_g: float, rule: dict) -> float:
    return round(rule.get("base", 0.6) + rule.get("per_gram", 0.004) * weight_g, 2)


def append_cost(db: Session, *, order_id: int | None, print_job_id: int | None,
                kind: str, amount: float, reason: str) -> CostLedger:
    entry = CostLedger(order_id=order_id, print_job_id=print_job_id, kind=kind, amount=amount, reason=reason)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    # 同步订单累计
    if order_id:
        order = db.get(Order, order_id)
        cost = dict(order.cost or {})
        cost[kind] = round(cost.get(kind, 0) + amount, 2)
        cost["total"] = round(cost.get("filament", 0) + cost.get("maintenance", 0) + cost.get("api", 0), 2)
        order.cost = cost
        db.commit()
    return entry


def append_api_usage(db: Session, *, kind: str, service: str, user_id: int | None,
                     input_tokens: int = 0, output_tokens: int = 0, points: float = 0.0,
                     unit_price: float = 0.0, meta: dict | None = None) -> ApiUsage:
    amount = round(input_tokens * unit_price / 1_000_000 + output_tokens * unit_price / 1_000_000 + points * unit_price, 4) \
        if service == "deepseek" else round(points * unit_price, 4)
    usage = ApiUsage(kind=kind, service=service, user_id=user_id, input_tokens=input_tokens,
                     output_tokens=output_tokens, points=points, unit_price=unit_price, amount=amount,
                     meta=meta or {})
    db.add(usage)
    db.commit()
    db.refresh(usage)
    return usage


def settle_order_costs(db: Session, order: Order, config: dict):
    """Val3 通过后成本核算（§11）：汇总该需求全部已完成打印任务的耗材费 + 维护费"""
    fee_cfg = config.get("fee", {})
    materials = {m["id"]: m for m in fee_cfg.get("materials", [])}
    material = materials.get(order.material_id, {})
    change_fee = fee_cfg.get("filament_change_fee", 1.5)
    maint_rule = fee_cfg.get("maintenance", {"base": 0.6, "per_gram": 0.004})
    done_jobs = [j for j in order.print_jobs if j.status == "done"]
    for job in done_jobs:
        rate = (order.reprint_rate or {}).get(str(job.seq), 1.0)  # 历史数据的折扣系数（现一律 1.0）
        fee = calc_filament_fee(material, job.actual_weight_g or job.est_weight_g, change_fee)
        amount = round(fee["total"] * rate, 2)
        reason = REPRINT_KINDS.get("MACHINE", "") if rate < 1 else f"打印 #{job.seq} 耗材费"
        append_cost(db, order_id=order.id, print_job_id=job.id, kind="filament", amount=amount,
                    reason=f"打印 #{job.seq} 耗材费（{reason}）" if rate < 1 else f"打印 #{job.seq} 耗材费")
    total_w = sum(j.actual_weight_g or j.est_weight_g for j in done_jobs)
    if done_jobs:
        append_cost(db, order_id=order.id, print_job_id=None, kind="maintenance",
                    amount=calc_maintenance(total_w, maint_rule), reason="维护费：打印头磨损等配件损耗摊分（§11.2）")
