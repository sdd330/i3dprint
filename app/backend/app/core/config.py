# E3DP backend — 应用配置（环境变量驱动，为服务器/内网穿透部署准备）
# 决策清单 §4：端口/数据路径/静态资源路径全走环境变量

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]  # backend/（core/config.py → app → backend）


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 服务
    app_name: str = "E3DP 校园3D打印活动平台"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # 数据存储（决策清单 §3：SQLite 起步，ORM 抽象可切 PostgreSQL）
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'e3dp.db'}"

    # 前端静态目录（打包后由后端托管，或独立部署时走 vite dev server）
    frontend_dist: str = str(BASE_DIR.parent / "frontend" / "dist")

    # 上传文件存储
    data_dir: str = str(BASE_DIR / "data")
    upload_dir: str = str(BASE_DIR / "data" / "uploads")

    # 安全（决策清单 §9）
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720  # 12h
    login_rate_limit_per_minute: int = 10  # 登录失败限流

    # 外部服务（决策清单 §5，API Key 走环境变量，不硬编码）
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_input_price_per_mtok: float = 0.0  # 元/百万token（活动前按实际填）
    deepseek_output_price_per_mtok: float = 0.0
    tripo_api_key: str = ""
    tripo_base_url: str = "https://api.tripo3d.ai/v2"
    tripo_price_per_point: float = 0.0  # 元/点

    # 切片器（设计文档 §6：OrcaSlicer CLI 服务端切片）
    orca_slicer_path: str = "orca-slicer"  # 可执行文件路径，未安装时走模拟切片
    slicer_mock: bool = True  # 未配置真切片器时用估算模拟（§12 首版模拟）

    # 合规声明（决策清单 §10）
    compliance_statement: str = "最终解释权归 FRC Team 6940 所有，任何人不得用作商业用途。"


settings = Settings()

# 确保数据目录存在
for d in [Path(settings.data_dir), Path(settings.upload_dir)]:
    d.mkdir(parents=True, exist_ok=True)
