# Violet Print — 手动数据库备份（只保留最近 2 份）
#
# 用法（backend/ 目录下）：
#   .venv/bin/python -m app.tools.backup_db           # 打一份快照并清理旧备份
#   .venv/bin/python -m app.tools.backup_db --list    # 只看现有备份
#
# 备份位置：backend/data/backups/e3dp-YYYYmmdd-HHMMSS.db（保留最近 2 份）
# 回滚方法：停服务 → cp 备份文件覆盖 data/e3dp.db → 启动

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

from ..core.config import settings

KEEP = 2


def backups_dir() -> Path:
    d = Path(settings.data_dir) / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path() -> Path:
    return Path(settings.database_url.replace("sqlite:///", "")) if settings.database_url.startswith("sqlite:///") else Path()


def prune(keep: int = KEEP) -> list[str]:
    removed = []
    for old in sorted(backups_dir().glob("e3dp-*.db"))[:-keep]:
        removed.append(old.name)
        old.unlink(missing_ok=True)
    return removed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="备份 SQLite 数据库（保留最近 2 份）")
    ap.add_argument("--list", action="store_true", help="只列出已有备份")
    ap.add_argument("--keep", type=int, default=KEEP, help="保留份数（默认 2）")
    args = ap.parse_args(argv)

    if args.list:
        for f in sorted(backups_dir().glob("e3dp-*.db")):
            print(f"  {f.name}  {f.stat().st_size/1024:.0f}KB")
        return 0

    src = db_path()
    if not src.exists() or src.stat().st_size == 0:
        print("数据库文件不存在或为空，无需备份")
        return 1
    dst = backups_dir() / f"e3dp-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
    shutil.copy2(src, dst)
    removed = prune(args.keep)
    print(f"已备份：{dst}")
    if removed:
        print("已清理旧备份：", ", ".join(removed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
