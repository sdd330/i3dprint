# Violet Print — 重置 root（受保护超级管理员）口令
#
# 用法（backend/ 目录下）：
#   .venv/bin/python -m app.tools.reset_root                  # 重置为随机强口令并打印
#   .venv/bin/python -m app.tools.reset_root --password xxx    # 重置为指定口令
#   .venv/bin/python -m app.tools.reset_root --activate        # 同时确保 root 启用且角色为 root

from __future__ import annotations

import argparse
import secrets
import sys

from ..core.database import Base, SessionLocal, engine
from ..core.security import hash_password
from ..models import Role, User


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="重置 root 超级管理员口令")
    ap.add_argument("--password", default="", help="指定新口令（不填则生成随机强口令）")
    ap.add_argument("--activate", action="store_true", help="同时确保 root 启用、角色为 root")
    args = ap.parse_args(argv)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        root_role = db.query(Role).filter_by(code="root").first()
        if not root_role:
            print("缺少 root 角色：请先启动一次服务（seed 会自动补建内置角色）")
            return 1
        user = db.query(User).filter_by(username="root").first()
        password = args.password or f"Root-{secrets.token_urlsafe(9)}"
        if len(password) < 6:
            print("口令至少 6 位")
            return 1
        if not user:
            user = User(username="root", name="超级管理员", grade="", contact="",
                        hashed_password=hash_password(password), role_id=root_role.id)
            db.add(user)
            print("已创建 root 账号")
        else:
            user.hashed_password = hash_password(password)
            if args.activate:
                user.role_id = root_role.id
                user.is_active = True
                print("已将 root 置为启用 + root 角色")
        db.commit()
        print(f"root 新口令：{password}")
        print("请登录后立刻用右上角「修改密码」更换。")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
