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

    # 上传限制（160MB 级大 OBJ 也可解析，但做上限防护）
    max_upload_bytes: int = 300 * 1024 * 1024
    # 几何分析超时（秒）：超过返回明确提示，不再无限阻塞
    analysis_timeout_sec: int = 90

    # 切片器（设计文档 §6：OrcaSlicer CLI 服务端切片，POC 通过后关闭 mock）
    orca_slicer_path: str = "/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer"
    slicer_mock: bool = True  # 未配置真切片器时用估算模拟（§12 首版模拟）
    slicer_max_concurrent: int = 2  # 云端切片最大并行数（软件设置可配）
    # X1C 内置 profile（CLI 正确用法：--load-settings "machine;process" + --load-filaments）
    orca_machine_profile: str = "/Applications/OrcaSlicer.app/Contents/Resources/profiles/BBL/machine/Bambu Lab X1 Carbon 0.4 nozzle.json"
    orca_process_profile: str = "/Applications/OrcaSlicer.app/Contents/Resources/profiles/BBL/process/0.20mm Standard @BBL X1C.json"
    orca_filament_profile: str = "/Applications/OrcaSlicer.app/Contents/Resources/profiles/BBL/filament/Bambu PLA Basic @BBL X1C.json"

    # 合规声明（决策清单 §10）
    compliance_statement: str = "最终解释权归 FRC Team 6940 所有，任何人不得用作商业用途。"


settings = Settings()

# 确保数据目录存在
for d in [Path(settings.data_dir), Path(settings.upload_dir)]:
    d.mkdir(parents=True, exist_ok=True)
