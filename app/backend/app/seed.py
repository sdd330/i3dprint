# E3DP backend — 种子数据
# 生成：默认活动模板（配置中心全量参数）/ 内置角色 / 示例用户 / 一个"开放中"活动

from sqlalchemy.orm import Session

from .core.security import hash_password
from .models import AppSetting, Campaign, ConfigTemplate, CostLedger, Model, ModelVersion, Order, PrintJob, QaKnowledge, Review, Role, User
from .models.entities import now_iso
from .models.permissions import DEFAULT_ROLES

# 配置中心 · 默认活动模板（决策清单 §14：全局基线，新建活动复制为活动参数副本）
DEFAULT_TEMPLATE_DATA = {
    "activity": {
        "max_participants": 20,
        "appeal_limit_per_campaign": 10,  # 每场活动申诉审核上限（§5.3）
        "appeal_limit_per_model": 3,      # 单模型申诉次数上限（§5.3）
        "notice": "本场为 3D 打印体验活动，非营利、费用仅覆盖成本。",
    },
    "fee": {
        # colors：该材料**实际有货**的颜色（打印需求页只展示这里的颜色，执行打印也按它备料）
        # 元素可以是 "#RRGGBB"，也可以是 {"name": "白", "hex": "#FFFFFF"}（带中文名更利于清单核对）
        "materials": [
            {"id": "pla", "name": "PLA 聚乳酸", "price_per_g": 0.10, "coeff": 1.0, "density": 1.24,
             "colors": [{"name": "白", "hex": "#F5F5F0"}, {"name": "黑", "hex": "#23262B"},
                        {"name": "橙", "hex": "#E8602C"}, {"name": "蓝", "hex": "#2B6CB0"},
                        {"name": "绿", "hex": "#2F855A"}, {"name": "灰", "hex": "#CBD5E0"}]},
            {"id": "petg", "name": "PETG 共聚酯", "price_per_g": 0.16, "coeff": 1.2, "density": 1.27,
             "colors": [{"name": "黑", "hex": "#23262B"}, {"name": "白", "hex": "#F5F5F0"},
                        {"name": "青", "hex": "#38B2AC"}]},
            {"id": "abs", "name": "ABS 工程塑料", "price_per_g": 0.14, "coeff": 1.15, "density": 1.04,
             "colors": [{"name": "黑", "hex": "#23262B"}, {"name": "白", "hex": "#F5F5F0"}]},
            {"id": "tpu", "name": "TPU 柔性材料", "price_per_g": 0.22, "coeff": 1.3, "density": 1.21,
             "colors": [{"name": "黑", "hex": "#23262B"}, {"name": "红", "hex": "#C53030"}]},
        ],
        "filament_change_fee": 1.5,      # 换料补偿（元/次）
        "maintenance": {"base": 0.6, "per_gram": 0.004},  # 维护费 = base + per_gram×重量
        "reprint_rate": {"PARAMETER": 1.0, "MACHINE": 1.0, "MODEL": 0.0, "MACHINE_LIMIT": 0.0, "OTHER": 1.0},  # 2026-10：取消设备问题半价
        "api": {"llm_input_per_mtok": 2.0, "llm_output_per_mtok": 8.0, "tripo_per_point": 0.1},  # 对话模型 token 单价（按实际用量计费）
    },
    "val1": {
        "build_volume": {"x": 256, "y": 256, "z": 256},  # X1C
        "wall_min_hard": 0.8, "wall_min_soft": 1.2,      # 壁厚（mm）
        "overhang_warn": 30, "overhang_hard": 55,        # 悬垂占比（%）
        "checks": ["integrity", "closed", "manifold", "self_intersect", "size", "wall", "overhang", "material", "params", "sliceable"],
    },
    "presets": [
        {"id": "fast", "name": "快速档", "layer_height": 0.28, "infill": 15, "speed": 120, "supports": "auto", "note": "速度快，细节一般，适合结构简单的模型"},
        {"id": "standard", "name": "标准档", "layer_height": 0.20, "infill": 20, "speed": 100, "supports": "auto", "note": "速度与质量均衡，日常推荐"},
        {"id": "fine", "name": "精细档", "layer_height": 0.12, "infill": 25, "speed": 80, "supports": "auto", "note": "细节好，耗时较长，适合小尺寸模型"},
    ],
    "print": {
        "reprint_rate_machine": 1.0,  # 设备问题重打（2026-10 取消半价）
        "queue_strategy": "fifo",     # 队列调度策略（§8.2）
        "anomaly_requeue": True,      # 中间环节异常→重新排队（§16.4）
        # 打印机清单（可增删/启停；忙闲状态由 print_service 运行时维护）
        "printers": [
            {"id": "x1c-01", "name": "X1C-01", "model": "Bambu Lab X1-Carbon", "enabled": True},
            {"id": "x1c-02", "name": "X1C-02", "model": "Bambu Lab X1-Carbon", "enabled": True},
        ],
    },
    # 强度档（打印需求页用户可选；映射为工艺参数，2026-10 起由配置中心维护）
    "strength_tiers": [
        {"id": "light", "name": "轻量", "desc": "展示摆件、不承力：耗材省、速度快",
         "layer_height": 0.24, "wall_loops": 2, "infill_density": 10, "top_shell_layers": 3,
         "bottom_shell_layers": 3, "infill_pattern": "grid"},
        {"id": "standard", "name": "标准", "desc": "日常推荐：质量与强度均衡",
         "layer_height": 0.20, "wall_loops": 2, "infill_density": 20, "top_shell_layers": 4,
         "bottom_shell_layers": 3, "infill_pattern": "grid"},
        {"id": "strong", "name": "坚固", "desc": "功能件、受力件：更厚壁、更高填充",
         "layer_height": 0.20, "wall_loops": 3, "infill_density": 40, "top_shell_layers": 5,
         "bottom_shell_layers": 4, "infill_pattern": "gyroid"},
        {"id": "ultra", "name": "超坚固", "desc": "承力结构件：耗材与时间显著增加",
         "layer_height": 0.16, "wall_loops": 4, "infill_density": 60, "top_shell_layers": 6,
         "bottom_shell_layers": 5, "infill_pattern": "cubic"},
    ],
    "compliance": {
        "list": ["管制刀具/武器类模型", "危险品（易燃易爆等）", "明显违规用途（作弊工具等）", "其他平台规定禁止的内容"],
        "statement": "最终解释权归 FRC Team 6940 所有，任何人不得用作商业用途。",
        "pickup_location": "创客空间 A 区货架（凭活动密码 + 需求编号取件）",
        "pickup_window": "活动次日 12:00-18:00",
        "contacts": [
            {"grade": "大一", "members": ["李同学 138****1024", "王同学 139****8876"]},
            {"grade": "大二", "members": ["张同学 137****3345", "刘同学 136****9901"]},
            {"grade": "大三", "members": ["陈同学 135****2210", "赵同学 133****5678"]},
            {"grade": "大四", "members": ["周同学 132****4456", "吴同学 131****7789"]},
        ],
    },
    "qa": {
        "system_prompt": (
            "你是校园3D打印活动平台「3D打印小屋」的站娘薇尔莉特，风格亲切俏皮。"
            "你只回答与本平台（3D打印、模型、Val1/Val2/Val3审核、切片、费用、取件）相关的问题；"
            "当前用户处于步骤：{step}。若用户询问无关内容，主动引导回打印主题。"
            "平台合规声明：{statement}"
        ),
        "filter_words": ["代打印外单", "商业接单", "违禁品代购"],
    },
}


# 软件全局设置清单（环境变量图形化配置的落地点）
APP_SETTINGS_META = [
    ("tripo_api_key", "external", "Tripo API Key", "AI 建模真实调用（留空为程序化演示）", "secret", False),
    ("llm_base_url", "external", "AI 对话 Endpoint", "任意 OpenAI 兼容地址：LM Studio http://127.0.0.1:1234/v1、DeepSeek https://api.deepseek.com/v1、OpenAI…", "str", False),
    ("llm_api_key", "external", "AI 对话 API Key", "本地模型（LM Studio/Ollama）一般留空；云端服务填 key", "secret", False),
    ("llm_max_concurrent", "external", "对话并发上限（0=自动）", "0=自动按端点判定：本地端点(LM Studio/Ollama) 1 个并发，在线 API（如非思考模式 ds-flash）4 个并发；填 >0 则强制指定", "int", False),
    ("llm_queue_timeout_sec", "external", "排队超时（秒）", "0/留空=自动（本地 40s / 在线 25s）；超过则提示用户稍后再问，避免请求堆积", "int", False),
    ("llm_model", "external", "AI 对话模型", "留空则自动取 /v1/models 中第一个对话模型；可在「站娘配置 → 对话模型」里一键切换", "str", False),
    ("embedding_enabled", "external", "启用本地向量检索", "站娘知识库用 embedding 做语义检索；关闭则回退 TF-IDF 词袋检索", "bool", False),
    ("embedding_base_url", "external", "Embedding 服务地址", "LM Studio 本地服务，形如 http://127.0.0.1:1234/v1（OpenAI 兼容）", "str", False),
    ("embedding_model", "external", "Embedding 模型", "如 text-embedding-text2vec-bge-large-chinese-i1（留空则自动从 /v1/models 探测）", "str", False),
    ("orca_slicer_path", "slicer", "OrcaSlicer 可执行文件路径", "CLI 切片器；macOS 指向 app 内二进制", "str", False),
    ("orca_machine_profile", "slicer", "打印机 profile", "X1C machine JSON（--load-settings 第 1 段）", "str", False),
    ("orca_process_profile", "slicer", "工艺 profile", "X1C process JSON（--load-settings 第 2 段）", "str", False),
    ("orca_filament_profile", "slicer", "耗材 profile", "--load-filaments 的 filament JSON", "str", False),
    ("slicer_mock", "slicer", "切片模拟开关", "true=估算模拟（标注模拟估算）；false=真实 OrcaSlicer", "bool", False),
    ("slicer_max_concurrent", "slicer", "最大并行切片数", "同时最多几个 OrcaSlicer 切片进程；超出排队等待（建议 2，单机 8 核）", "int", False),
    ("max_upload_bytes", "service", "模型上传上限（字节）", "超过则拒绝上传", "int", False),
    ("analysis_timeout_sec", "service", "几何分析超时（秒）", "仅生僻格式回退 trimesh 子进程时生效；STL/OBJ 走快速解析（秒级内）", "int", False),
    ("kb_vector_min_score_dense", "service", "教材检索·语义阈值", "稠密向量相似度阈值（0.34 较稳；调高更严格，容易落到大模型）", "float", False),
    ("kb_vector_min_score", "service", "教材检索·字面阈值", "TF-IDF 字面相似度阈值（默认 0.06）", "float", False),
    ("kb_vector_hybrid_sparse_weight", "service", "教材检索·字面权重", "混合分 = 语义分 + 该权重 × 字面分（默认 0.45）", "float", False),
    ("wall_raycast_enabled", "service", "精确壁厚（抽样射线）", "默认关闭：壁厚用 2V/A 快速估算（薄壳件即壁厚）。开启后对闭合模型抽样投射射线取 5 分位，更准但慢", "bool", False),
    ("wall_ray_samples", "service", "壁厚采样射线数", "开启精确壁厚时的采样数（越大越准越慢，建议 800）", "int", False),
    ("wall_raycast_max_faces", "service", "精确壁厚面数上限", "超过该面数不抽样（避免慢），退回 2V/A 估算", "int", False),
    ("jwt_secret", "service", "JWT 密钥", "生产环境务必修改。更改后：① 所有登录会话失效；② 已保存的 API Key（DeepSeek/Tripo）将无法解密，需在软件设置中重新填写", "secret", True),
    ("compliance_statement", "misc", "平台合规声明", "展示于首页/审核界面（FRC Team 6940）", "str", False),
]


def seed(db: Session):
    # 软件全局设置（环境变量图形化配置落地点，决策清单 P5）
    # upsert：已存在行仅同步元数据（label/hint/分类），保留用户设置的 value；缺失行以 env 默认值插入
    from .core.config import settings
    from .core.secrets_util import encrypt_secret
    for key, cat, label, hint, vtype, restart in APP_SETTINGS_META:
        row = db.query(AppSetting).filter_by(key=key).first()
        if row:
            row.label, row.hint, row.category, row.value_type, row.restart_required = label, hint, cat, vtype, restart
        elif hasattr(settings, key):
            val = str(getattr(settings, key))
            if vtype == "secret" and val:
                val = encrypt_secret(val)  # secret 加密落库
            db.add(AppSetting(key=key, value=val, category=cat,
                              label=label, hint=hint, value_type=vtype, restart_required=restart))
    db.commit()

    # 迁移：api 单价键 deepseek_* → llm_*（模板与各活动副本）
    def _migrate_api_keys(data: dict) -> bool:
        api = ((data or {}).get("fee") or {}).get("api")
        if not isinstance(api, dict):
            return False
        changed = False
        for old, new in (("deepseek_input_per_mtok", "llm_input_per_mtok"),
                         ("deepseek_output_per_mtok", "llm_output_per_mtok")):
            if old in api and new not in api:
                api[new] = api.pop(old)
                changed = True
        return changed

    for tpl_row in db.query(ConfigTemplate).all():
        import copy as _c
        data = _c.deepcopy(tpl_row.data or {})
        if _migrate_api_keys(data):
            tpl_row.data = data
    for camp in db.query(Campaign).all():
        import copy as _c
        cfg = _c.deepcopy(camp.config or {})
        if _migrate_api_keys(cfg):
            camp.config = cfg
    db.commit()

    # 迁移：并发/超时改为"0=自动"后，把旧默认值 1 / 40 迁成 0（只迁移仍是旧默认的行）
    for key, old in (("llm_max_concurrent", "1"), ("llm_queue_timeout_sec", "40")):
        row = db.query(AppSetting).filter_by(key=key).first()
        if row and (row.value or "").strip() == old:
            row.value = "0"
    db.commit()

    # 清理历史 DeepSeek 专用设置（2026-10 起统一用通用 llm_base_url / llm_api_key / llm_model）
    for legacy in ("deepseek_api_key", "deepseek_base_url", "deepseek_model"):
        row = db.query(AppSetting).filter_by(key=legacy).first()
        if row:
            db.delete(row)
    db.commit()

    # 角色（RBAC，决策清单 §9）
    if db.query(Role).count() == 0:
        for code, cfg in DEFAULT_ROLES.items():
            db.add(Role(code=code, name=cfg["name"], permissions=cfg["permissions"], builtin=True))
        db.commit()
    else:
        # 老库：内置角色缺失则补建（如新增的 root）；已存在的补齐权限点（不删管理员手动调过的）
        changed = False
        for code, cfg in DEFAULT_ROLES.items():
            role = db.query(Role).filter_by(code=code, builtin=True).first()
            if not role:
                db.add(Role(code=code, name=cfg["name"], permissions=cfg["permissions"], builtin=True))
                changed = True
                continue
            current = list(role.permissions or [])
            missing = [p for p in cfg["permissions"] if p not in current]
            if missing:
                role.permissions = current + missing
                changed = True
        if changed:
            db.commit()

    # 默认活动模板（老库补齐新增分类/子键；已有值一律保留）
    from .services.config_service import _merge_defaults

    tpl = db.query(ConfigTemplate).filter_by(is_default=True).first()
    if tpl is None:
        db.add(ConfigTemplate(name="默认活动模板", is_default=True, data=DEFAULT_TEMPLATE_DATA))
        db.commit()
    else:
        import copy as _copy
        data = _copy.deepcopy(tpl.data or {})
        merged = _merge_defaults(data, DEFAULT_TEMPLATE_DATA)
        if merged != data:
            tpl.data = merged
            db.commit()

    # 示例用户
    if db.query(User).count() == 0:
        admin_role = db.query(Role).filter_by(code="admin").first()
        stu_role = db.query(Role).filter_by(code="student").first()
        # 只创建 root（最底层管理员）与 admin（日常负责人）；
        # 学生账号由学生自助注册（/api/auth/register）或负责人在「用户管理」创建
        root_role_id = db.query(Role).filter_by(code="root").first().id
        db.add_all([
            User(username="root", name="超级管理员", grade="", contact="",
                 hashed_password=hash_password(getattr(settings, "root_password", "root123456")),
                 role_id=root_role_id),
            User(username="admin", name="平台负责人", grade="", contact="admin@stu.edu.cn",
                 hashed_password=hash_password("admin123"), role_id=admin_role.id),
        ])
        db.commit()

    # 兜底：老库没有 root 账号时补建（受保护账号必须存在）
    if not db.query(User).filter_by(username="root").first():
        root_role = db.query(Role).filter_by(code="root").first()
        if root_role:
            db.add(User(username="root", name="超级管理员", grade="", contact="",
                        hashed_password=hash_password(getattr(settings, "root_password", "root123456")),
                        role_id=root_role.id))
            db.commit()

    # 站娘知识库初始条目（决策清单 §13：管理端可图形化增删改查）
    if db.query(QaKnowledge).count() == 0:
        kb = [
            ("参数,标准档,层高,填充,怎么选", "参数设置", "happy",
             "对参数零基础的同学直接用「标准档」就好～快速档层高 0.28mm 快但细节一般，标准档 0.2mm 质量均衡，精细档 0.12mm 细节最好但慢。进阶同学可以选手动模式。"),
            ("耗材,材料,pla,petg,abs,tpu,选哪个", "耗材选择", "happy",
             "PLA 最常用，便宜好打，摆件首选；PETG 更韧更耐温，适合功能件；ABS 强度高但容易翘边；TPU 是软的，适合保护套。材料直接影响费用和难度～"),
            ("费用,多少钱,收费,成本,价格", "费用查看", "coin",
             "平台非营利，只收成本：耗材费 = 材料成本价 × 重量 × 系数（+ 换料补偿），加维护费（打印头磨损摊分）和 API 用量费。活动结束统一核算收款，不逐单支付～"),
            ("val1,审核,能不能打印,标记,人工复核", "Val1 审核", "think",
             "Val1 是模型能不能打印的自动检查：封闭、非流形、自交、尺寸、壁厚、悬垂等。全部通过就直接进入「打印需求配置」；一旦有潜在问题，系统会**标记**并转给负责人人工复核（不会退回你重做），复核结果是放行 / 建议修改模型 / 不可打印。"),
            ("打印需求,强度,参数,清单,材料", "打印需求", "happy",
             "Val1 之后在「打印需求」页选材料、强度和进阶参数。强度分轻量/标准/坚固/超坚固（自动对应壁厚圈数与填充率），进阶可手动改层高、填充、支撑。提交后会生成一张打印清单交给执行打印的负责人——当前版本不做在线切片。"),
            ("val3,验收,实物", "Val3 验收", "warn",
             "Val3 是打印完的实物验收：结构、翘边、层间分离、表面质量、关键尺寸。不通过会判定问题责任：参数→改打印需求重打、设备→重打、模型→改模型重走 Val1、设备能力上限→终止。"),
            ("取件,取单,密码", "取件", "happy",
             "每场活动有一个「活动密码」，打印完成收到取件通知后，凭活动密码 + 需求编号到指定地点取件。密码每场更新，活动结束失效～"),
            ("自备耗材,自带", "创建需求", "happy",
             "可以自带耗材：交给负责人，检验合格（规格/状态/支持类型）后才开始打印，不合格会暂停任务并通知你。"),
            ("退回,重做,为什么要审核,不通过", "Val1 审核", "think",
             "现在没有「自动退回」了：Val1 发现问题只会在你的订单上打标记并转人工复核，由负责人判断能不能放行。只有负责人明确要求修改模型时，你才需要改模型后重新提交。"),
            ("摆放,旋转,缩放,阵列,吸底,自动摆放", "模型摆放", "happy",
             "摆放界面可以直接拖拽移动、旋转、缩放手柄：按 G/R/S 或点右侧「移动/旋转/缩放」切换，带 1mm / 15° / 0.05 倍吸附；还支持吸底、自动摆放、按毫米精确缩放、阵列。零基础直接点自动摆放 + 吸底～"),
            ("ai建模,生成模型,没有模型", "AI 建模", "magic",
             "没有现成模型可以用 AI 建模：提交草图/图片/文字描述+尺寸要求即可生成。生成后自动做打印体检，没问题就能下载或直接填充到上传环节，照走全部审核～"),
        ]
        for keywords, step, anim, answer in kb:
            db.add(QaKnowledge(keywords=keywords.split(","), question=keywords.split(",")[0],
                               answer=answer, step_context=step, animation_key=anim))
        db.commit()

    # 示例活动（开放中，继承默认模板生成参数副本）
    if db.query(Campaign).count() == 0:
        tpl = db.query(ConfigTemplate).filter_by(is_default=True).first()
        campaign = Campaign(
            name="2026 秋季第 1 场 · 3D 打印体验活动",
            status="开放中",
            password="E3DP-AUTUMN",
            open_at="2026-08-28T09:00:00",
            close_at="2026-08-29T18:00:00",
            max_participants=20,
            config=tpl.data,  # 活动参数副本（继承自默认模板）
        )
        db.add(campaign)
        db.commit()

    # 历史数据迁移（在线切片/Val2 暂缓）：旧状态 → 新链路，幂等
    migrate_legacy_statuses(db)

    # 知识库向量化（backend/kb/*.md → kb_sources / kb_chunks，按文件哈希幂等）
    try:
        from .services.kb_vector import sync_all
        synced = sync_all(db)
        for item in synced:
            if item.get("changed"):
                print(f"[kb] 已建向量索引：{item['name']} → {item['chunks']} 块 / {item['tokens']} 词")
    except Exception as e:  # 知识库同步失败不影响启动
        print(f"[kb] 知识库同步失败：{e}")


def migrate_legacy_statuses(db: Session):
    """历史数据迁移：在线切片 + Val2 暂缓后，旧状态统一映射到新链路（幂等）。

    val1_appeal（旧「警告/申诉」）→ val1_review（标记 + 人工复核）
    slicing / val2_pending / val2_failed（旧切片链路）→ print_config（打印需求配置）
    说明：仅改订单状态与时间轴，历史 slice 快照保留（不删数据）。
    """
    from .models import Order
    mapping = {"val1_appeal": "val1_review", "slicing": "print_config",
               "val2_pending": "print_config", "val2_failed": "print_config"}
    changed = 0
    for order in db.query(Order).filter(Order.status.in_(list(mapping))).all():
        old = order.status
        order.status = mapping[old]
        note = {"val1_review": "（历史数据迁移）旧「Val1 警告/申诉」→ 标记 + 人工复核",
                "print_config": "（历史数据迁移）在线切片暂缓，旧切片环节 → 打印需求配置"}[order.status]
        order.timeline = list(order.timeline or []) + [
            {"t": now_iso(), "status": order.status, "note": note}]
        changed += 1
    if changed:
        db.commit()
    return changed
