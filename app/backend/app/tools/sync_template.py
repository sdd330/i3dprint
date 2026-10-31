# Violet Print — 把当前活动参数同步到默认模板
#
# 用法（backend/ 目录下）：
#   .venv/bin/python -m app.tools.sync_template            # 当前活动 → 默认模板
#   .venv/bin/python -m app.tools.sync_template --dry-run   # 只看会同步哪些分类
#
# 说明：只影响"以后新建的活动"继承的基线；正在跑的活动副本不受影响。

from __future__ import annotations

import argparse
import json
import sys

from ..core.database import Base, SessionLocal, engine
from ..services.campaign_service import get_current_campaign
from ..services.config_service import CATEGORIES, get_default_template, sync_template_from_campaign


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="同步当前活动参数到默认模板")
    ap.add_argument("--dry-run", action="store_true", help="只列出差异，不写入")
    ap.add_argument("--operator", default="cli", help="审计里的操作人")
    args = ap.parse_args(argv)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        camp = get_current_campaign(db)
        if not camp:
            print("没有活动")
            return 1
        tpl = get_default_template(db)
        cfg = dict(camp.config or {})
        print(f"来源活动：{camp.name}（#{camp.id}）→ 默认模板：{tpl.name}")
        changed = []
        for cat in CATEGORIES:
            if cat not in cfg:
                continue
            if (tpl.data or {}).get(cat) != cfg[cat]:
                changed.append(cat)
        print("有差异的分类：", changed or "（无，模板已一致）")
        if args.dry_run or not changed:
            return 0
        result = sync_template_from_campaign(db, camp, operator=args.operator)
        print("已同步：", result["synced"])
        d = get_default_template(db).data or {}
        print("模板打印机：", [p.get("id") for p in (d.get("print") or {}).get("printers", [])])
        print("模板材料颜色：", [(m["id"], len(m.get("colors") or [])) for m in (d.get("fee") or {}).get("materials", [])])
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
