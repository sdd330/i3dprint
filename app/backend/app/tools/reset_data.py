# Violet Print backend — 生产迁移：清理测试数据
#
# 用法（在 backend/ 目录下）：
#   .venv/bin/python -m app.tools.reset_data --dry-run        # 先看会删什么
#   .venv/bin/python -m app.tools.reset_data --yes            # 清订单/模型/流水/日志（保留用户与配置）
#   .venv/bin/python -m app.tools.reset_data --yes --drop-demo-users   # 连演示学生账号一起删
#
# 保留：角色/权限、活动与配置（含材料颜色/强度档/打印机/演示模型）、站娘知识库与向量索引。
# 删除：订单全链路（订单/打印任务/审核/问题/费用流水/模型与版本）、API 用量、问答工单、
#       配置与操作审计日志、上传的模型文件与切片产物。

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from ..core.config import settings
from ..core.database import Base, SessionLocal, engine
from ..models import (
    ApiUsage, AuditLog, ConfigAudit, CostLedger, Issue, KbChunk, KbSource, Model, ModelVersion,
    Order, PrintJob, QaTicket, QaTicketComment, Review, User,
)

DEMO_USERNAMES = ("20260001", "20260002", "20260003")

TABLES = [
    ("费用流水", CostLedger), ("API 用量", ApiUsage), ("问题记录", Issue), ("审核记录", Review),
    ("打印任务", PrintJob), ("订单", Order), ("模型版本", ModelVersion), ("模型", Model),
    ("问答工单回复", QaTicketComment), ("问答工单", QaTicket),
    ("配置审计", ConfigAudit), ("操作日志", AuditLog),
]
KEEP = [("用户", User), ("知识库来源", KbSource), ("知识库切块", KbChunk)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="清理 Violet Print 的测试数据（生产迁移用）")
    ap.add_argument("--yes", action="store_true", help="确认执行（不加则只做 dry-run）")
    ap.add_argument("--dry-run", action="store_true", help="只统计不修改（默认行为，显式写出来更清晰）")
    ap.add_argument("--drop-demo-users", action="store_true",
                    help="同时删除演示学生账号（20260001-3），保留 admin")
    ap.add_argument("--keep-files", action="store_true", help="保留 uploads/slices 文件（默认删除）")
    args = ap.parse_args(argv)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        print(f"数据库：{settings.database_url}")
        print("=== 将删除 ===")
        for label, model in TABLES:
            n = db.query(model).count()
            print(f"  {label:12s} {n} 行")
        if args.drop_demo_users:
            n = db.query(User).filter(User.username.in_(DEMO_USERNAMES)).count()
            print(f"  {'演示账号':12s} {n} 个（{', '.join(DEMO_USERNAMES)}）")
        print("=== 将保留 ===")
        for label, model in KEEP:
            print(f"  {label:12s} {db.query(model).count()} 行")
        print("  活动 / 配置模板 / 角色权限 / 软件设置")

        uploads = Path(settings.upload_dir)
        slices = Path(settings.data_dir) / "slices"
        for d in (uploads, slices):
            if d.exists():
                n = len(list(d.glob("*")))
                print(f"  文件目录 {d}：{n} 个文件{'（将删除）' if not args.keep_files else '（保留）'}")

        if not args.yes:
            print("\n[dry-run] 未做任何修改。确认无误后加 --yes 执行。")
            return 0

        for _, model in TABLES:
            db.query(model).delete()
        if args.drop_demo_users:
            db.query(User).filter(User.username.in_(DEMO_USERNAMES)).delete()
        db.commit()

        if not args.keep_files:
            for d in (uploads, slices):
                if d.exists():
                    shutil.rmtree(d, ignore_errors=True)
                    d.mkdir(parents=True, exist_ok=True)
        print("\n已清理完成。建议：重启服务，并检查「配置中心 / 软件设置」是否符合生产要求。")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
