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
        "materials": [
            {"id": "pla", "name": "PLA 聚乳酸", "price_per_g": 0.10, "coeff": 1.0, "density": 1.24},
            {"id": "petg", "name": "PETG 共聚酯", "price_per_g": 0.16, "coeff": 1.2, "density": 1.27},
            {"id": "abs", "name": "ABS 工程塑料", "price_per_g": 0.14, "coeff": 1.15, "density": 1.04},
            {"id": "tpu", "name": "TPU 柔性材料", "price_per_g": 0.22, "coeff": 1.3, "density": 1.21},
        ],
        "filament_change_fee": 1.5,      # 换料补偿（元/次）
        "maintenance": {"base": 0.6, "per_gram": 0.004},  # 维护费 = base + per_gram×重量
        "reprint_rate": {"PARAMETER": 1.0, "MACHINE": 1.0, "MODEL": 0.0, "MACHINE_LIMIT": 0.0, "OTHER": 1.0},  # 2026-10：取消设备问题半价
        "api": {"deepseek_input_per_mtok": 2.0, "deepseek_output_per_mtok": 8.0, "tripo_per_point": 0.1},
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
    },
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
            "你是校园3D打印活动平台「3D打印小屋」的站娘店长，风格亲切俏皮。"
            "你只回答与本平台（3D打印、模型、Val1/Val2/Val3审核、切片、费用、取件）相关的问题；"
            "当前用户处于步骤：{step}。若用户询问无关内容，主动引导回打印主题。"
            "平台合规声明：{statement}"
        ),
        "filter_words": ["代打印外单", "商业接单", "违禁品代购"],
    },
}


# 软件全局设置清单（环境变量图形化配置的落地点）
APP_SETTINGS_META = [
    ("deepseek_api_key", "external", "DeepSeek API Key", "站娘问答真实调用（留空为模拟回答）", "secret", False),
    ("deepseek_base_url", "external", "DeepSeek Base URL", "OpenAI 兼容接口地址", "str", False),
    ("deepseek_model", "external", "DeepSeek 模型", "如 deepseek-chat", "str", False),
    ("tripo_api_key", "external", "Tripo API Key", "AI 建模真实调用（留空为程序化演示）", "secret", False),
    ("orca_slicer_path", "slicer", "OrcaSlicer 可执行文件路径", "CLI 切片器；macOS 指向 app 内二进制", "str", False),
    ("orca_machine_profile", "slicer", "打印机 profile", "X1C machine JSON（--load-settings 第 1 段）", "str", False),
    ("orca_process_profile", "slicer", "工艺 profile", "X1C process JSON（--load-settings 第 2 段）", "str", False),
    ("orca_filament_profile", "slicer", "耗材 profile", "--load-filaments 的 filament JSON", "str", False),
    ("slicer_mock", "slicer", "切片模拟开关", "true=估算模拟（标注模拟估算）；false=真实 OrcaSlicer", "bool", False),
    ("slicer_max_concurrent", "slicer", "最大并行切片数", "同时最多几个 OrcaSlicer 切片进程；超出排队等待（建议 2，单机 8 核）", "int", False),
    ("max_upload_bytes", "service", "模型上传上限（字节）", "超过则拒绝上传", "int", False),
    ("analysis_timeout_sec", "service", "几何分析超时（秒）", "仅生僻格式回退 trimesh 子进程时生效；STL/OBJ 走快速解析（秒级内）", "int", False),
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

    # 角色（RBAC，决策清单 §9）
    if db.query(Role).count() == 0:
        for code, cfg in DEFAULT_ROLES.items():
            db.add(Role(code=code, name=cfg["name"], permissions=cfg["permissions"], builtin=True))
        db.commit()

    # 默认活动模板
    if db.query(ConfigTemplate).count() == 0:
        db.add(ConfigTemplate(name="默认活动模板", is_default=True, data=DEFAULT_TEMPLATE_DATA))
        db.commit()

    # 示例用户
    if db.query(User).count() == 0:
        admin_role = db.query(Role).filter_by(code="admin").first()
        stu_role = db.query(Role).filter_by(code="student").first()
        users = [
            User(username="admin", name="负责人 · 老韩", grade="研二", contact="admin@stu.edu.cn",
                 hashed_password=hash_password("admin123"), role_id=admin_role.id),
            User(username="20260001", name="小陈", grade="大一", contact="chen@stu.edu.cn",
                 hashed_password=hash_password("123456"), role_id=stu_role.id),
            User(username="20260002", name="阿宁", grade="大二", contact="ning@stu.edu.cn",
                 hashed_password=hash_password("123456"), role_id=stu_role.id),
            User(username="20260003", name="小周", grade="大三", contact="zhou@stu.edu.cn",
                 hashed_password=hash_password("123456"), role_id=stu_role.id),
        ]
        db.add_all(users)
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
             "可以自带耗材：放到平台指定位置（保险柜），负责人检验合格（规格/状态/支持类型）后才开始打印，不合格会暂停任务并通知你。"),
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

        # 示例订单（各阶段演示数据）
        users = {u.username: u for u in db.query(User).all()}
        stu1, stu2, stu3 = users["20260001"], users["20260002"], users["20260003"]
        from datetime import datetime, timedelta
        t = datetime.utcnow()

        # 内置演示模型（与前端 Workspace 一致）
        from .services.val1 import analyze_mesh, build_preset
        presets = {}
        for kind in ("vase", "stand", "spinner"):
            mesh = build_preset(kind)
            presets[kind] = analyze_mesh(mesh)
        m_vase = Model(owner_id=stu1.id, name="内置模型 · vase", kind="preset")
        db.add(m_vase); db.flush()
        db.add(ModelVersion(model_id=m_vase.id, version=1, file_path="preset:vase", stats=presets["vase"]))
        m_stand = Model(owner_id=stu2.id, name="内置模型 · stand", kind="preset")
        db.add(m_stand); db.flush()
        db.add(ModelVersion(model_id=m_stand.id, version=1, file_path="preset:stand", stats=presets["stand"]))
        m_spin = Model(owner_id=stu3.id, name="内置模型 · spinner", kind="preset")
        db.add(m_spin); db.flush()
        db.add(ModelVersion(model_id=m_spin.id, version=1, file_path="preset:spinner", stats=presets["spinner"]))
        db.flush()

        def iso(dt): return dt.isoformat(timespec="seconds")

        # O1 已完成（vase；新链路：Val1 → 打印需求 → 清单 → 打印 → 验收 → 核算）
        o1 = Order(campaign_id=campaign.id, user_id=stu1.id, model_id=m_vase.id,
                   model_version_id=db.query(ModelVersion).filter_by(model_id=m_vase.id).first().id,
                   name="内置模型 · vase", status="completed", material_id="pla", color="#2B6CB0",
                   params={"strength": "standard", "strength_name": "标准", "supports": "auto",
                           "layer_height": 0.2, "wall_loops": 2, "infill_density": 20, "infill_pattern": "grid"},
                   placement={"rotation": [0, 0, 0], "scale": 1, "position": [0, 0, 0]},
                   geometry={"bbox": presets["vase"]["bbox"]},
                   val1={"result": "通过", "summary": "模型满足制造条件，可通过", "stats": presets["vase"],
                         "flagged": False, "flagged_items": []},
                   cost={"filament": 2.54, "maintenance": 0.7, "api": 0, "total": 3.24},
                   timeline=[
                       {"t": iso(t - timedelta(days=2)), "status": "draft", "note": "创建打印需求"},
                       {"t": iso(t - timedelta(days=2)), "status": "modeling", "note": "完成模型摆放：吸底 + 自动摆放"},
                       {"t": iso(t - timedelta(days=2)), "status": "val1_pending", "note": "提交 Val1 自动审核"},
                       {"t": iso(t - timedelta(days=2)), "status": "print_config", "note": "Val1 通过（无潜在问题），进入打印需求配置"},
                       {"t": iso(t - timedelta(days=2, hours=-1)), "status": "queued", "note": "打印需求已提交（PLA / 标准强度），生成打印清单 #1"},
                       {"t": iso(t - timedelta(days=1, hours=2)), "status": "printing", "note": "X1C-01 开始打印"},
                       {"t": iso(t - timedelta(days=1, hours=1)), "status": "val3_pending", "note": "打印完成，等待实物验收"},
                       {"t": iso(t - timedelta(hours=20)), "status": "settlement", "note": "Val3 验收通过，成本核算"},
                       {"t": iso(t - timedelta(hours=19)), "status": "completed", "note": "结清，计入活动账单"},
                   ], created_at=iso(t - timedelta(days=2)))
        db.add(o1); db.flush()
        pj1 = PrintJob(order_id=o1.id, seq=1, printer_id="x1c-01", status="done",
                       est_time_sec=9300, est_weight_g=19.3, actual_weight_g=20.1,
                       gcode={"source": "estimate", "manifest": {
                           "order_id": o1.id, "name": o1.name, "material": {"id": "pla", "name": "PLA 聚乳酸"},
                           "color": o1.color, "strength": {"id": "standard", "name": "标准"},
                           "bbox": presets["vase"]["bbox"]}},
                       started_at=iso(t - timedelta(days=1, hours=2)),
                       ended_at=iso(t - timedelta(days=1, hours=1)), note="清单 #1：PLA · 标准强度 · 19.3g（估算）")
        db.add(pj1); db.flush()
        db.add(CostLedger(order_id=o1.id, print_job_id=pj1.id, kind="filament", amount=2.54, reason="打印 #1 耗材费"))
        db.add(CostLedger(order_id=o1.id, kind="maintenance", amount=0.7, reason="维护费：打印头磨损摊分（§11.2）"))
        for stage, res, reviewer, note in [
            ("val1", "通过", "系统", "自动审核全部通过"), ("val3", "通过", "负责人 · 老韩", "结构完整，表面良好")]:
            db.add(Review(order_id=o1.id, stage=stage, result=res, reviewer=reviewer, note=note))

        # O2 已提交打印需求 → 在打印清单里等负责人执行（stand，自备耗材待检验）
        o2 = Order(campaign_id=campaign.id, user_id=stu2.id, model_id=m_stand.id,
                   model_version_id=db.query(ModelVersion).filter_by(model_id=m_stand.id).first().id,
                   name="内置模型 · stand", status="queued", material_id="petg", color="#38B2AC",
                   params={"strength": "strong", "strength_name": "坚固", "supports": "auto",
                           "layer_height": 0.2, "wall_loops": 3, "infill_density": 40, "infill_pattern": "gyroid",
                           "operator_note": "手机支架承力，请勿减薄壁厚"},
                   placement={"rotation": [0, 0, 0], "scale": 1, "position": [0, 0, 0]},
                   geometry={"bbox": presets["stand"]["bbox"]}, self_filament=True,
                   val1={"result": "通过", "summary": "模型满足制造条件，可通过", "stats": presets["stand"],
                         "flagged": False, "flagged_items": []},
                   cost={"filament": 0, "maintenance": 0, "api": 0, "total": 0},
                   timeline=[
                       {"t": iso(t - timedelta(hours=5)), "status": "draft", "note": "创建打印需求"},
                       {"t": iso(t - timedelta(hours=5)), "status": "modeling", "note": "完成模型摆放"},
                       {"t": iso(t - timedelta(hours=4)), "status": "val1_pending", "note": "提交 Val1"},
                       {"t": iso(t - timedelta(hours=4)), "status": "print_config", "note": "Val1 通过，进入打印需求配置"},
                       {"t": iso(t - timedelta(hours=2)), "status": "queued", "note": "打印需求已提交（PETG / 坚固强度），自备耗材待检验"},
                   ], created_at=iso(t - timedelta(hours=5)))
        db.add(o2); db.flush()
        db.add(PrintJob(order_id=o2.id, seq=1, status="blocked", est_time_sec=14100, est_weight_g=11.6,
                        gcode={"source": "estimate", "manifest": {
                            "order_id": o2.id, "name": o2.name, "material": {"id": "petg", "name": "PETG 共聚酯"},
                            "color": o2.color, "strength": {"id": "strong", "name": "坚固"},
                            "bbox": presets["stand"]["bbox"], "operator_note": "手机支架承力，请勿减薄壁厚"}},
                        note="清单 #1：PETG · 坚固强度 · 11.6g（估算） · 自备耗材待检验（§16.3）"))
        db.add(Review(order_id=o2.id, stage="val1", result="通过", reviewer="系统", note="自动审核通过"))

        # O3 Val1 标记潜在问题 → 人工复核队列（不退回用户）
        o3 = Order(campaign_id=campaign.id, user_id=stu3.id, model_id=m_spin.id,
                   model_version_id=db.query(ModelVersion).filter_by(model_id=m_spin.id).first().id,
                   name="内置模型 · spinner", status="val1_review", material_id="pla", color="#D69E2E",
                   params=None, placement={"rotation": [0, 0, 0], "scale": 1, "position": [0, 0, 0]},
                   geometry={"bbox": presets["spinner"]["bbox"]},
                   val1={"result": "警告", "summary": "存在 2 项潜在风险：非流形结构、薄壁 0.6mm",
                         "flagged": True,
                         "stats": presets["spinner"],
                         "flagged_items": [
                             {"id": "manifold", "name": "非流形结构", "level": "warn", "message": "检测到非流形结构，切片可能出现异常"},
                             {"id": "wall", "name": "壁厚", "level": "warn", "message": "最小壁厚 0.6mm，接近极限"},
                         ],
                         "items": [
                             {"id": "manifold", "name": "非流形结构", "level": "warn", "message": "检测到非流形结构，切片可能出现异常"},
                             {"id": "wall", "name": "壁厚", "level": "warn", "message": "最小壁厚 0.6mm，接近极限"},
                         ]},
                   cost={"filament": 0, "maintenance": 0, "api": 0, "total": 0},
                   timeline=[
                       {"t": iso(t - timedelta(hours=8)), "status": "draft", "note": "创建打印需求"},
                       {"t": iso(t - timedelta(hours=7)), "status": "modeling", "note": "完成模型摆放"},
                       {"t": iso(t - timedelta(hours=6)), "status": "val1_pending", "note": "提交 Val1"},
                       {"t": iso(t - timedelta(hours=6)), "status": "val1_review", "note": "Val1 标记 2 项潜在问题（非流形结构、壁厚），转负责人人工复核（不退回用户）"},
                   ], created_at=iso(t - timedelta(hours=8)))
        db.add(o3); db.flush()
        db.add(Review(order_id=o3.id, stage="val1", result="警告", reviewer="系统", note="非流形 + 薄壁 0.6mm"))
        db.commit()


    # 历史数据迁移（在线切片/Val2 暂缓）：旧状态 → 新链路，幂等
    migrate_legacy_statuses(db)


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
