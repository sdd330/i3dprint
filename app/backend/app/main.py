# E3DP backend — FastAPI 应用入口

import socket
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .core.config import settings
from .core.database import Base, SessionLocal, engine
from .core.dynamic_settings import load_from_db
from .seed import seed
import logging


def _snapshot_db() -> None:
    """启动时给 SQLite 做一份时间点快照：配置被误改/误删时可回滚。"""
    import shutil
    from datetime import datetime
    src = Path(settings.database_url.replace("sqlite:///", "")) if settings.database_url.startswith("sqlite:///") else None
    if not src or not src.exists() or src.stat().st_size == 0:
        return
    backups = Path(settings.data_dir) / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    KEEP = 2                                     # 只保留最近 2 份快照
    existing = sorted(backups.glob("e3dp-*.db"))
    import time as _t
    if existing and _t.time() - existing[-1].stat().st_mtime < 1800:
        return                                   # 半小时内已有快照，跳过
    dst = backups / f"e3dp-{datetime.now().strftime('%Y%m%d-%H%M')}.db"
    try:
        shutil.copy2(src, dst)
        for old in sorted(backups.glob("e3dp-*.db"))[:-KEEP]:
            old.unlink(missing_ok=True)
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    log = logging.getLogger("uvicorn.error")
    if settings.jwt_secret in ("dev-secret-change-me", "", "dev-secret"):
        log.warning("安全提示：JWT_SECRET 仍是默认值，生产环境务必在「软件设置 → 服务」或环境变量中修改")
    _snapshot_db()                      # 先备份，再做任何建表/迁移写入
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed(db)
        from .services.campaign_service import rotate_weak_access_passwords
        for camp in rotate_weak_access_passwords(db):
            log.warning("活动「%s」还在用历史默认口令，已换成随机口令——"
                        "新口令请到「活动管理」查看，并按线下方式重新告知学生", camp.name)
        try:
            from .core.security import verify_password
            from .models import User
            admin = db.query(User).filter(User.username == "admin").first()
            if admin and verify_password("admin123", admin.hashed_password):
                log.warning("安全提示：管理员账号仍是默认口令 admin123，请在「角色管理」里尽快修改")
        except Exception:
            pass
        load_from_db(db)  # 加载持久化的软件设置覆盖（环境变量图形化配置）
    # 局域网访问地址（部署到局域网服务器时，学生用 http://<这台机器的IP>:端口 打开）
    port = _runtime_port()
    for ip in _lan_ips():
        log.info("局域网访问：http://%s:%s", ip, port)
    if sys.platform == "darwin":
        log.info("macOS 提示：若手机/其他电脑打不开而本机能开，多半是「本地网络」隐私授权没给——"
                 "系统设置 → 隐私与安全性 → 本地网络，把运行本服务的 App（终端/iTerm/mimo 等）打开，然后重启服务")
    yield


def _runtime_port() -> int:
    """实际监听端口：优先取命令行 --port（uvicorn 不写回 settings），否则用配置值。"""
    import sys
    argv = sys.argv
    for i, arg in enumerate(argv):
        if arg == "--port" and i + 1 < len(argv):
            try:
                return int(argv[i + 1])
            except ValueError:
                return settings.port
        if arg.startswith("--port="):
            try:
                return int(arg.split("=", 1)[1])
            except ValueError:
                return settings.port
    return settings.port


def _lan_ips() -> list[str]:
    ips = set()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ips.add(info[4][0])
    except Exception:
        pass
    try:
        s_ = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s_.connect(("8.8.8.8", 80))   # 不真的发包，只用来拿默认出口地址
        ips.add(s_.getsockname()[0])
        s_.close()
    except Exception:
        pass
    return sorted(i for i in ips if not i.startswith("127."))


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# 开发期前端 dev server 跨域（部署后同源托管，可收紧）
_cors = [o.strip() for o in (settings.cors_origins or "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors or ["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"ok": True, "app": settings.app_name, "port": _runtime_port(),
            "frontend_served": (Path(settings.frontend_dist) / "index.html").exists()}


# 路由
from .routers import admin, ai, auth, config, meta, orders, qa
from .routers import settings as settings_router
from .routers.printers import router as printer_router
from .routers.users import router as users_router

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(meta.router, prefix="/api/meta", tags=["meta"])
app.include_router(orders.router, prefix="/api", tags=["orders"])
app.include_router(admin.router, prefix="/api", tags=["admin"])
app.include_router(config.router, prefix="/api", tags=["config"])
app.include_router(qa.router, prefix="/api/qa", tags=["qa"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(settings_router.router, prefix="/api", tags=["settings"])
app.include_router(printer_router)  # /api/printers（配置中心维护设备清单）
app.include_router(users_router, prefix="/api")   # /api/admin/users（用户管理，需要 user:manage）


# ---------- 前端静态托管（同源部署：学生只要访问本机 http://<IP>:<port>）----------
_dist = Path(settings.frontend_dist)
if _dist.exists():
    _assets = _dist / "assets"
    if _assets.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        """已构建的前端：优先返回 dist 里的真实文件，其余交给 index.html（Vue history 路由）。"""
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail="接口不存在")
        candidate = (_dist / full_path).resolve()
        try:
            # 防目录穿越：解析后必须仍在 dist 内
            candidate.relative_to(_dist.resolve())
        except ValueError:
            raise HTTPException(status_code=404, detail="Not Found")
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_dist / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def dev_hint():
        return {
            "app": settings.app_name,
            "hint": "未找到前端构建产物（frontend/dist）。开发时请用 npm run dev；"
                    "部署时先 `cd frontend && npm run build`，本服务会自动同源托管。",
            "api_health": "/api/health",
        }
