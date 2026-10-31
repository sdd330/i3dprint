# E3DP · 校园3D打印活动平台（短期活动版）

基于《校园3D打印平台设计-短期活动版.docx》（17章）与 `../实现决策清单.md`（14 项决策 + 站娘补充全部已定）实现的全功能首版。

**技术栈**（决策清单）：Python FastAPI + SQLAlchemy + SQLite（ORM 可切 PostgreSQL）｜ Vue3 + Vite + Element Plus + Three.js（本地托管，不依赖 CDN）

## 快速开始

### 后端（默认端口 8000）

```bash
cd backend
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/uvicorn app.main:app --port 8000        # 首次启动自动建库 + 种子数据
```

> 可选：`cd backend/native && ./build.sh` 编译原生 STL 解析器（不编译也可运行，会自动回退 numpy 实现）。

### 前端（默认端口 5173）

```bash
cd frontend
npm install
npm run dev        # /api 自动代理到 localhost:8000
```

浏览器打开 http://localhost:5173

### 演示账号

| 角色 | 账号 | 密码 |
|---|---|---|
| 学生 | `20260001`（小陈）/ `20260002`（阿宁）/ `20260003`（小周） | `123456` |
| 负责人 | `admin` | `admin123` |

## 本期变更（2026-10）

| 变更 | 说明 |
|---|---|
| **在线切片 / Val2 暂停** | 移除用户端在线切片与 Val2 切片核验（接口与 `ParamsConfig.vue` 下线，`services/slicing.py` 保留待恢复）。`/api/meta/bootstrap` 暴露 `flow.online_slicing=false`、`flow.val2_review=false`，前端据此隐藏入口 |
| **Val1 无退回机制** | Val1 只做自动判定：全部通过 → `print_config`；出现警告/不通过项 → **标记**（`val1.flagged / flagged_items`）并转 `val1_review` 人工复核 queue，用户端不再有「申诉/被退回」概念。负责人可 放行 / 要求修改模型 / 终止 |
| **打印需求 → 打印清单** | 新增 `POST /api/orders/{id}/print-requirement`：材料 + 强度档（轻量/标准/坚固/超坚固，映射壁厚圈数与填充率）+ 进阶参数（OrcaSlicer 同名）+ 执行人备注 → 保存为结构化清单并生成 `PrintJob`（耗材/时长按几何量**估算**，标注 `source=estimate`，不冒充切片结果） |
| **打印清单页** | 负责人端 `/admin/manifest` 整页清单（可 `window.print()`）；工作台打印队列直接展示材料/强度/参数/尺寸/预估/备注，并支持下载模型、耗材检验、开始打印 |
| **摆放交互改进** | 直接按住模型在平台平面拖动（1mm 吸附 + 越界回弹）；TransformControls 三轴手柄（G 移动 / R 旋转 15° 吸附 / S 缩放 0.05 吸附）；百分比滑块 + 按毫米精确缩放（等比/单轴，后端按三轴 scale 换算体积/壁厚/bbox）；F 聚焦；修掉 `v-loading` 遮罩挡住画布导致视角无法拖拽的老问题 |
| **收费信息隐去** | `flow.billing_visible=false`：首页/订单/设置/审计等处的费用与账单 UI 全部隐藏（后端计费逻辑与流水保留，置 true 即恢复） |
| **AI 建模入口暂时关闭** | `flow.ai_modeling=false`：导航栏/首页/CreateOrder 引导里的入口全部隐藏，`/ai` 页面顶部显示"暂时关闭"横幅且禁用生成（后端 `/api/ai/generate` 与按量计费保留，置 true 即恢复） |
| **负责人工作台改纵向 + 清单精简** | 各审核卡改为**纵向单列**；打印清单每行**只显示材料（含颜色色块/自备耗材标记）**，**操作按钮优先显示**（开始打印 / 清单 / 模型 / 耗材合格），强度·参数·尺寸·预估等细节收进「清单」弹窗 |
| **打印中可手动填写时间** | `POST /api/admin/print/{job_id}/time`：负责人可填/改**开始时间**与**预计时长（分钟）**，覆盖几何估算值；进度条按「开始时间 + 预计时长」推算，改动即时生效并写审计 |
| **取消设备问题半价重打** | Val3 判定设备问题后只进入「重新打印」，不再写 `reprint_rate=0.5`；配置默认 `fee.reprint_rate.MACHINE` / `print.reprint_rate_machine` 同步改 1.0，界面文案统一为「重打」 |
| **打印机数量可配** | 设备清单进配置中心：`print.printers`（id / 名称 / 型号 / 启用开关，可增删）。`print_service` 只维护运行时忙闲状态，`/api/printers`、`/admin/queues`、`/meta/bootstrap` 全部读配置（此前 `PRINTERS` 写死 2 台，且 `/api/printers` 的路由从未挂载 → 一直 404） |
| **UI 设计语言更新（Violet Print）** | 全站切换到 Pantone Violet C（#582C83）色系；项目正式名 **Violet Print**，站娘 **薇尔莉特（Violet）**；清除全部 emoji；队徽 `sign.jpg` 用作顶栏 logo + 首页横幅 + 左侧底纹；教程页右上角浮 `tutorial.png` 并在首章引导站娘面板用法；站娘面板改为**右侧抽屉**（平时只露竖排标签+箭头，点击滑出），顶部按对话状态切换 `normal / happy / shocked` 三张立绘；资产经 `sips` 压到合适尺寸放 `public/brand/` |
| **计费键名通用化 + 计费 UI 继续隐藏** | `fee.api` 单价键 `deepseek_input/output_per_mtok` → **`llm_input/output_per_mtok`**（启动时自动迁移模板与各活动副本）；`ApiUsage.service` 记为 `llm`，输入/输出可分别定价（`append_api_usage(output_unit_price=…)`）。**计费内容仍不展示**：配置中心「费用参数」里价格/系数/换料补偿/维护费/重打比例/API 单价整块隐藏（材料的名称/密度/有货颜色照常维护）；检索阈值等 3 个参数补进「软件设置 → 服务」可调 |
| **AI 对话改通用端点（2026-10）** | 去掉 DeepSeek 专用配置：`llm_base_url` / `llm_api_key` / `llm_model` 指向任意 OpenAI 兼容 `/v1`（LM Studio、Ollama、DeepSeek、OpenAI、vLLM）；`GET /admin/llm/status` 列模型（自动过滤 embedding 模型）、`POST /admin/llm/model` 一键切换即时生效、`POST /admin/llm/test` 试跑。界面在「站娘配置 → 对话模型」；历史 `deepseek_*` 设置行启动时自动清理 |
| **闲聊拉回主题 + 并发排队** | 与打印无关的问题（天气/笑话/写诗）不再查教材也不占用模型，直接返回固定话术把话题拉回 3D 打印；领域内问题才走向量/模型。并发**按端点自动判定**：本机/局域网端点（LM Studio、Ollama、192.168/10.x…）串行 1 个、排队超时 40s；在线 API（生产用非思考模式 ds-flash 等）并发 4 个、排队超时 25s；`llm_max_concurrent=0` 为自动，填 >0 强制覆盖。`GET /api/qa/llm/queue` 暴露 running/waiting，面板显示「前面还有 N 个提问在处理」 |
| **线下负责人配置修复** | 编辑器把 `members` 数组当字符串绑定，保存后首页 `.join()` 失效——现按「顿号分隔文本 ↔ 数组」双向转换；同时配置中心默认切到「当前活动」副本并提示「编辑默认模板只影响新建活动」，避免"改了不生效" |
| **教材向量知识库** | 见上「站娘知识库：本地向量检索」小节：`backend/kb/*.md` 自动切块建 TF-IDF 索引，问答命中即引用教材章节，负责人端可同步/调试 |
| **活动（场次）管理界面** | 新增 `/admin/campaigns`：活动列表（状态/时间窗口/人数上限/取件密码/订单统计/参数来源）、新建（参数可继承默认模板或指定场次）、编辑基本信息、**切换当前活动**、生命周期流转（含「重新开放」，误点归档可恢复）、删除（仅限无订单场次）、账单入口。「当前活动」指针落 `AppSetting.current_campaign_id`，学生端/工作台/配置中心/打印清单统一按它取场次（此前硬编码"最新一场"，无法切换） |
| **耗材颜色绑定到材料** | 材料增加 `colors` 清单（`#RRGGBB` 或 `{name, hex}`，配置中心「费用参数 → 材料」按材料维护）；打印需求页只展示所选材料**实际有货**的颜色并显示中文名，切换材料自动落到该材料的首个颜色；提交时后端校验颜色属于该材料（否则 400 并列出可选色）；清单/订单/工作台显示颜色名 |
| **打印参数档真正接入** | 「强度档」进配置中心（`strength_tiers` 分类，可增删档位、改层高/壁厚圈数/填充率/顶底实心层/图案），打印需求页与 `merge_params` 直接读配置；修复配置中心保存接口把 `data` 限定为 `dict` 导致**列表型分类（参数档/强度档）保存必 422** 的老 bug |

## 站娘知识库：本地向量检索（2026-10）

`backend/kb/*.md`（当前收录 `6940_3d_printing.md` 队内 3D 打印教材，74KB / 1347 行）会被自动切块并建立**稀疏向量索引**，站娘问答按顺序命中：
关键词条目（`QaKnowledge`）→ **教材向量检索** → DeepSeek（未配置 key 时走模拟）。

| 环节 | 做法 |
|---|---|
| 切块 | 按 Markdown 标题层级切（保留章节路径），单块 ≤420 字、<40 字丢弃，过长按段落再切 |
| 分词 | 中文「单字 + 相邻二元组」（无需词典依赖），英文/数字按词；单字权重 0.45、二元组 1.0、英文 1.3；标题权重 ×2 |
| 向量 | TF-IDF（sublinear tf × idf）后 L2 归一化，存 `kb_chunks.vector`；idf 表存 `kb_sources.idf` 供查询复用 |
| 检索（混合） | **稠密 embedding + 稀疏 TF-IDF**：语义分 = max(正文向量, 标题向量) 余弦；字面分 = TF-IDF 余弦；综合 = `语义 + 0.45×字面 + 字面命中加成`。入场门槛：语义 ≥ `kb_vector_min_score_dense`（默认 0.30）或字面 ≥ `kb_vector_min_score`（默认 0.06）。命中即作答并标注「来自教材 · 章节路径」 |
| Embedding | 本地 **LM Studio**（OpenAI 兼容 `/v1/embeddings`，默认 `http://127.0.0.1:1234/v1`，模型 `text-embedding-text2vec-bge-large-chinese-i1`，1024 维，单位化后存库）。地址/模型/开关在「软件设置 → 外部服务」；服务不可用自动回退纯 TF-IDF |
| 同义归一 | 折叠常见写法差异（第一层→首层、黏→粘、填充率→填充、喷头→喷嘴…），提升召回 |
| 同步 | 启动时按文件哈希幂等同步；负责人端「站娘配置 → 教材知识库」可增量同步 / 强制重建 / 检索调试 |

零外部 API、零费用、可离线；将来接真实 embedding（bge/m3e 等本地模型）时只需替换 `vectorize()` 与 `search()` 两个函数。
实测（dense+hybrid，教材 108 块）："首层粘不住怎么办" → 3.4 涂胶（0.42）、"填充率设多少比较结实" → 8.3 稀疏填充（0.71）、"支撑能不用吗" → 4.6 支撑（0.57）、"STEP 和 STL 差在哪" → 1.3（0.75）、"孔和轴怎么配合" → 4.4（0.59）；纯稀疏模式下仍可用（如 4.6 得 0.17）。重建整库约 9 秒（108 块 × 2 通道向量）。

## 原生 STL 解析器（C，2026-10）

上传阶段只需要"预览级"几何信息，因此 STL 解析改为独立 C 实现，思路对照 OrcaSlicer / admesh
（`deps_src/admesh/stlinit.cpp::stl_open_count_facets`、`shared.cpp::stl_generate_shared_vertices`）：

| 环节 | 做法 |
|---|---|
| 二进制/ASCII 判定 | 首个面记录 128 字节内有无 >127 字节 + `84 + n×50 == file_size` 双向校验；**面数以文件大小为准**，头部声明值只做对照（头部被改也能读） |
| 读取 | `mmap` 零拷贝 + 50 字节定长跨步（法线 12 + 顶点 36 + 属性 2），跳过含 NaN 的三角 |
| 顶点去重 | 坐标量化成 64 位键（包围盒对角线 / 2²¹）→ **LSD 基数排序** → 按 rank 分配索引（确定性、无哈希碰撞） |
| 拓扑 | 无向边键排序后"每条边出现 2 次"→ 封闭；有向边键相邻重复 → 缠绕不一致（非流形） |
| 统计 | 包围盒 / 表面积 / 有向体积（散度定理）/ 悬垂占比（法线 z < −sin45°） |
| 壁厚 | `2V/A`（薄壳件即壁厚；实心件给出体量厚度，不误报"过薄"）。**不再逐面投射射线**——旧实现是 O(面数²)，96k 面即卡死数十秒 |
| 超大模型 | 面数 > 2,000,000 时跳过拓扑（省下数百 MB 峰值），返回 `topology_note` 提示 |

**实测（本机 x86_64 Python / Intel 容器化环境）**

| 文件 | 面数 | 旧实现（trimesh + 逐面射线） | numpy 版 | **C 版** |
|---|---|---|---|---|
| `Violet 3DP_fixed.stl`（4.8MB） | 96,684 | 卡住（>60s 未返回） | 110 ms | **24–35 ms** |
| `sphere_328k.stl`（16MB） | 327,680 | 数十秒 | 313 ms | **95–130 ms** |
| `sphere_1310k.stl`（65MB） | 1,310,720 | 不可用 | 1.28 s | **375–525 ms** |

端到端上传（HTTP + 落盘 + 解析）：目标文件 **50–60 ms**，65MB 大文件 **0.62 s**。
C / numpy / trimesh 三方的 bbox、面积、体积、封闭性、流形性逐项一致（含 ASCII STL、开口网格、NaN 面、错误头部等边界用例）。

**编译方式**

```bash
cd backend/native && ./build.sh      # macOS 出 universal2（x86_64+arm64），Linux 出 .so
```

- 产物不入库；**首次调用会自动编译一次**（检测到 `cc` 才做），失败或无编译器时静默回退 numpy 实现，功能不受影响。
- 为什么 macOS 要 `-arch x86_64 -arch arm64`：本机 Python 可能是 Intel/Rosetta 版，而 clang 默认按当前机器出 arm64，单一架构会 `dlopen` 失败。
- 需要更精确的壁厚时，在「软件设置 → 服务」打开 `wall_raycast_enabled`（抽样射线，5 分位，默认关闭）。

## 功能一览

**打印主链**（§4-§11，2026-10 调整版）：创建需求 → 选模型/上传 STL（服务端 trimesh 真实几何分析）→ 类 Bambu 摆放工作区（直接拖拽 / 三轴手柄 / 滑块与毫米精确缩放 / 吸底锁定 / 自动摆放 / 阵列，Three.js）→ Val1 自动审核 →**通过**直接进入「打印需求」/**有潜在问题**则打标记转负责人人工复核（**不自动退回**）→ 打印需求配置（材料 + 强度档 + 进阶参数 + 给执行人备注）→ 生成**打印清单**（负责人据此在切片软件中执行）→ 打印执行（模拟 Provider，预留拓竹 LAN）→ Val3 验收 + 责任判定（参数→改打印需求重打/设备半价/模型新版本重走 Val1/设备上限终止）→ 结算完成。

**两级状态机**（§12）：活动 4 态（待开放/开放中/收尾中/已归档）× 订单多态（Val1 新增 `val1_review` 人工复核、`print_config` 打印需求配置；`slicing`/`val2_*` 暂缓保留兼容历史数据），问题类型与状态分离。启动时自动迁移旧状态（`val1_appeal→val1_review`、`slicing/val2_*→print_config`）。

**独立模块**：AI 建模（Tripo SDK 占位，按用量计费 + 就地打印体检，可自动填充到上传环节）；站娘问答（知识库 + DeepSeek 按 token 计费 + 输出监督：自监督 prompt + 过滤词双向检测 + 警示注入对话历史 + GitHub Issue 式工单）。

**配置中心**（§14）：默认模板 + 活动参数副本**可选继承**（继承模板/上一场），8 类参数（活动/费用/Val1 阈值/打印档位/打印设备/合规/站娘/权限）图形化编辑、改动即时生效、修改审计。

**权限系统**（§9）：学号+密码（bcrypt+JWT）、RBAC 角色可配置（与模块权限解耦）、资源级归属校验（越权 403）、审计日志（操作人+时间+IP）、登录限流。

## 环境变量（`.env`，为服务器部署准备，§4）

| 变量 | 默认 | 说明 |
|---|---|---|
| `HOST` / `PORT` | 0.0.0.0 / 8000 | 监听地址 |
| `DATABASE_URL` | `sqlite:///backend/data/e3dp.db` | 可切 PostgreSQL |
| `JWT_SECRET` | dev-secret-change-me | **生产必须修改** |
| `DEEPSEEK_API_KEY` | 空 | 站娘问答真实调用；为空时返回模拟回答 |
| `TRIPO_API_KEY` | 空 | AI 建模真实调用（未接时为程序化演示） |
| `ORCA_SLICER_PATH` / `SLICER_MOCK` | orca-slicer / true | 服务端切片器；POC 后关闭 mock |

## 生产部署（活动期间）

1. `npm run build` 产出 `frontend/dist`，后端自动托管（`FRONTEND_DIST` 指向它）——同源部署，无需 CORS
2. 单机 + 内网穿透（frp / cloudflared / ngrok）暴露公网，穿透工具自带 HTTPS
3. 修改 `JWT_SECRET`、配置 DeepSeek/Tripo key、按采购价填配置中心费用表

## 目录结构

```
backend/
  app/
    core/        # 配置(database_url等环境变量) / 数据库 / 安全(bcrypt+JWT+RBAC+审计+限流)
    models/      # 实体(活动/用户/订单/模型/打印任务/审核/费用流水/配置中心/工单) + 权限点
    services/    # 状态机 / Val1(trimesh) / 切片(OrcaSlicer预留+模拟) / 费用 / 打印模块(Provider接口)
                 # 配置中心(模板+继承+审计) / 站娘(DeepSeek+知识库+监督) / Tripo
    routers/     # auth / meta / orders(主链) / admin(审核队列+打印+活动+账单) / config / qa / ai
    seed.py      # 种子：默认模板 / 角色 / 用户 / 活动 / 各状态示例订单 / 站娘知识库
frontend/
  src/
    views/       # 学生端：Home/Login/OrderList/OrderDetail/CreateOrder/Workspace(Three.js)/AiModeling/Manual
    views/admin/ # 负责人：AdminHome(审核队列+打印+活动+账单)/ConfigCenter/RoleManage/QaConfig/AuditLogs
    components/  # StatusTag / ChainView(主链状态轴) / QaPanel(站娘浮动)
```

## 待办（POC 后接入）

- §6.4 真机 POC：OrcaSlicer CLI 无 X 跑通 → 切片预测数据从 3MF/gcode 提取（当前 mock 标注来源）
- 拓竹 LAN Provider 实现（`services/print_service.py` 的 `PrintProvider` 接口）
- Tripo AI SDK 真实调用（当前程序化生成 + 用量占位）
- Spine 动画资产接入（知识库动画关键字已预留）
