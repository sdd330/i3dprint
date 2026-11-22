# API

路由文件即路由：`server/api/**/*.get.ts` / `*.post.ts`，`server/routes/**` 负责页面级路由。
本页按鉴权级别分组；鉴权实现见 [architecture.md](architecture.md)。

## 公开（OAuth 流程，不带会话）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/oauth/authorize` | 登录并签发授权码（前置 `vz_verifier`/`vz_state` cookie；限流 `IP:用户名`） |
| GET | `/oauth/callback`（routes） | OAuth 回调页 |
| POST | `/api/oauth/token` | 授权码换令牌 / 刷新令牌轮换（校验 `client_id`） |
| POST | `/api/oauth/logout` | 登出，清会话 Cookie 并作废令牌 |
| POST | `/api/oauth/revoke` | 撤销令牌 |

## 登录用户（`requireUser`）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/me` | 当前用户 |
| GET | `/api/home` | 首页数据（staff 看全局，学生按 `user.id` 过滤） |
| GET | `/api/campaigns` | 活动列表 |
| GET | `/api/models` | 模型列表 |
| GET | `/api/models/[code]` | 模型详情 |
| GET | `/api/orders` | 订单列表 |
| POST | `/api/orders` | 创建打印需求（`params` 走合并更新，不整列覆盖） |
| GET | `/api/orders/[code]` | 订单详情 |
| POST | `/api/orders/[code]/print` | 提交打印 |
| POST | `/api/account/password` | 改口令（字符串化后再验长度，堵数字绕过） |

## 教工（`requireStaff`）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/desk/[view]` | 工作台视图 |
| GET | `/api/admin/users` | 用户管理 |
| GET | `/api/admin/roles` | 角色管理 |
| GET | `/api/admin/settings` | 全局设置 |
| GET | `/api/admin/audits` | 配置审计 |
| GET | `/api/admin/manifest` | 清单 |

## 错误契约

见 [architecture.md#error-契约](architecture.md#错误契约)：503 数据库不可用、500 服务端错误、堆栈不进响应、文案走 `message`。
