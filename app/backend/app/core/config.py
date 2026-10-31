# E3DP backend — 应用配置（环境变量驱动，为服务器/内网穿透部署准备）
# 决策清单 §4：端口/数据路径/静态资源路径全走环境变量

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]  # backend/（core/config.py → app → backend）


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 服务
    app_name: str = "Violet Print · 校园 3D 打印自助平台"
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
    jwt_secret: str = "dev-secret-change-me"  # 生产必须改（启动会告警）
    # 首次建库时 root（最底层管理员）的初始口令；生产请用 E3DP_ROOT_PASSWORD 覆盖
    root_password: str = "root123456"
    # 生产部署把这里改成实际域名（同源部署可留空）；默认只放行本地开发端口
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
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
    # AI 对话（2026-10）：任意 OpenAI 兼容端点（LM Studio / DeepSeek / OpenAI / Ollama…）
    llm_base_url: str = "http://127.0.0.1:1234/v1"
    llm_api_key: str = ""          # 本地模型通常不需要；云端填 key
    llm_model: str = ""            # 留空=自动取 /v1/models 里第一个对话模型
    llm_max_concurrent: int = 0    # 0=自动：本地端点 1 / 在线端点 4；>0 手动指定
    llm_queue_timeout_sec: int = 0   # 0=自动（本地 40s / 在线 25s）

    # 向量检索 embedding（2026-10）：本地 LM Studio / 任意 OpenAI 兼容 /v1/embeddings
    embedding_enabled: bool = True
    embedding_base_url: str = "http://127.0.0.1:1234/v1"
    embedding_model: str = "text-embedding-text2vec-bge-large-chinese-i1"

    # 教材/手册向量检索阈值（2026-10，可在软件设置里调）
    kb_vector_min_score_dense: float = 0.34   # 语义通道阈值（本地/在线 embedding）
    kb_vector_min_score: float = 0.06         # 字面（TF-IDF）通道阈值
    kb_vector_hybrid_sparse_weight: float = 0.45  # 混合分中字面分权重

    # 壁厚测量（2026-10）：默认用 2V/A 快速估算；需要精确值时开启抽样射线
    wall_raycast_enabled: bool = False
    wall_ray_samples: int = 800
    wall_raycast_max_faces: int = 60000

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
