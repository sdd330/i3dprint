# E3DP backend — FastAPI 应用入口

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .core.database import Base, SessionLocal, engine
from .core.dynamic_settings import load_from_db
from .seed import seed
import logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    log = logging.getLogger("uvicorn.error")
    if settings.jwt_secret in ("dev-secret-change-me", "", "dev-secret"):
        log.warning("安全提示：JWT_SECRET 仍是默认值，生产环境务必在「软件设置 → 服务」或环境变量中修改")
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed(db)
        try:
            from .core.security import verify_password
            from .models import User
            admin = db.query(User).filter(User.username == "admin").first()
            if admin and verify_password("admin123", admin.hashed_password):
                log.warning("安全提示：管理员账号仍是默认口令 admin123，请在「角色管理」里尽快修改")
        except Exception:
            pass
        load_from_db(db)  # 加载持久化的软件设置覆盖（环境变量图形化配置）
    yield


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
    return {"ok": True, "app": settings.app_name}


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
