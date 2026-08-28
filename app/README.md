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

## 功能一览

**打印主链**（§4-§11）：创建需求 → 选模型/上传 STL（服务端 trimesh 真实几何分析）→ 类 Bambu 摆放工作区（旋转/平移/缩放/吸底/自动摆放/阵列，Three.js）→ Val1（10 项检查，阈值来自配置中心）→ 耗材/参数（标准档或进阶）→ 切片（预计时间/重量标注来源：切片器 or 模拟）→ Val2（自动检查 + 负责人人工审核 + 内容合规）→ 打印队列（模拟 Provider，预留拓竹 LAN）→ Val3 验收 + 责任判定（参数全价重打/设备半价/模型新版本重走 Val1/设备上限终止）→ 费用核算（耗材 + 维护 + API 用量，活动后统一收款）。

**两级状态机**（§12）：活动 4 态（待开放/开放中/收尾中/已归档）× 订单 16 态，问题类型与状态分离。

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
