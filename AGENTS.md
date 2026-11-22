# AGENTS.md

面向编码智能体的项目说明。改代码前先读完本文件；架构细节见 [docs/](docs/README.md)。

## 项目

TEAM 6940 校园三维打印（Violet Z）。Nuxt 4 SSR 读 MySQL 8，OAuth 2.1 登录。pnpm 12
workspace，唯一包 `apps/web`。技术栈与版本见 [docs/development.md](docs/development.md)。

## 命令（仓库根）

```bash
pnpm dev        # 开发
pnpm build      # 构建
pnpm lint       # oxlint
pnpm fmt        # oxfmt 写入
pnpm --filter @i3dprint/web typecheck   # 双通道: app(tsc --runExternalCode) + server
```

三绿才算完成：lint、typecheck、build。提交前自跑，不许留红。

## 硬规则

1. **不用 vue-tsc**。类型检查走 TS 7.1 content mappers：`tsc --runExternalCode` +
   `@vue/content-mapper` 注册在 tsconfig 顶层 `contentMappers`（与 `compilerOptions`
   平级，不在其内部）。vue-tsc 与 TS 7 永久不兼容，上游已定调废弃。`.vue` 的 script
   与 template 都在检查范围；`server/**` 走第二个通道 `.nuxt/tsconfig.server.json`。
2. **SQL 一律参数化**（`db.query(sql, params)`），禁止拼接，表名也不插值。
3. **SSR 数据获取用 `useFetch`**（带 Cookie），禁止 `useAsyncData` + `$fetch`——
   SSR 阶段丢 Cookie 首屏必 401。
4. **口令/令牌只存摘要**：登录 scrypt（N=2^17,r=8,p=1）、令牌 SHA-256、活动准入口令
   SM3。明文禁止落库。
5. **错误文案走 `message`**，不放 `statusMessage`（h3 剥非 ASCII）；堆栈只进服务端
   日志；库异常 503、其它 500。
6. **敏感信息不进仓库**：连接串、口令读 `~/.mysql_env` 或环境变量。
7. **`db/e3dp_schema.sql` 是 schema 权威**，命名/类型/状态字典遵循
   [docs/database-design.md](docs/database-design.md)（表名 `t_` 前缀、`valid=0` 逻辑
   删除、禁 float/double、金额分/重量毫克）。改表先改脚本再改代码。

## 布局速查

```
apps/web/app/        页面、组件、stores、layouts
apps/web/server/
  api/               REST（文件即路由，.get/.post 后缀；鉴权矩阵见 docs/api.md）
  routes/            页面路由（OAuth 回调）
  middleware/        oauth-prepare、session-refresh
  utils/             db、http、oauth、session、password
apps/web/shared/     前后端共享类型
db/e3dp_schema.sql   建表脚本
docs/                架构/API/开发/数据库设计
```

## 常见坑

- oxlint 是门禁；oxfmt 配置键名 `singleQuote`/`semi`/`printWidth`，写错键被静默忽略
- 刷新令牌轮换与 Cookie 写回在 `session-refresh` 中间件（含请求头改写，防二次轮换）
- OAuth 是公开客户端 + PKCE S256（`violet-z`），别改成 confidential 流程
- `X-Forwarded-For` 无置信反代时可伪造，限流/审计 IP 不做硬防护承诺
