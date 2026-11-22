# 架构

## 技术栈

| 层 | 选型 | 版本 |
|---|---|---|
| 包管理 | pnpm workspace | 12.21 |
| 框架 | Nuxt SSR（Nitro 服务端） | 4.6.4 |
| 语言 | TypeScript | 7.0.2 |
| 界面 | Vue、Vue Router | 3.5.44 / 5 |
| 状态 | Pinia（@pinia/nuxt） | 4.1.0 |
| 样式 | UnoCSS，presetWind4 | 66.13 |
| PWA | @vite-pwa/nuxt：可安装、autoUpdate、离线回退、maskable 图标 | 2.0.3 |
| 数据 | MySQL 8，服务端 `mysql2/promise` 连接池 | — |
| 检查与格式 | oxlint、oxfmt | 1.94 / 0.79 |

## SSR 数据流

页面在服务端用 `useFetch` 请求 Nitro 接口。`useFetch` 会原样转发浏览器 Cookie，
服务端渲染时接口能读到会话；不要改回 `useAsyncData` + `$fetch`——那会在 SSR
阶段丢掉 Cookie，首屏一律 401。

接口经 `server/utils/db.ts` 的 `getDb()` 取连接池，SQL 一律参数化（`db.query(sql, params)`）。

## 目录

```
apps/web/
  app/            页面、组件、layouts、stores、路由中间件
  server/
    api/          REST 接口（文件即路由，.get/.post 后缀）
    routes/       页面路由（OAuth 回调）
    middleware/   Nitro 中间件（oauth-prepare、session-refresh）
    utils/        db、http、oauth、session、password 等服务端工具
  shared/         前后端共享类型
  scripts/        seed-root.mjs、mysql-env.ts
db/e3dp_schema.sql  建表脚本，库名 i3dprint
```

## 中间件

| 文件 | 职责 |
|---|---|
| `server/middleware/oauth-prepare.ts` | OAuth 流程前置（verifier/state cookie） |
| `server/middleware/session-refresh.ts` | GET 页面渲染前完成刷新令牌轮换，把新 Cookie 写回响应；只在「无 access、有 refresh」时查库；跳过 `/api/`、`/oauth/`、`/_nuxt/`、`/__nuxt` 与 `/login` |

## 鉴权流程

OAuth 2.1 授权码 + PKCE S256，公开客户端 `violet-z`，回调 `/oauth/callback`。

1. `/login` 页发起授权：`/api/oauth/authorize` 前置写 `vz_verifier`、`vz_state` cookie。
2. 用户名口令认证：口令用 scrypt（N=2^17，r=8，p=1，16 字节随机盐，32 字节密钥）
   校验 `t_sys_user.password_hash`，比对用 `timingSafeEqual`。
3. 认证成功签发授权码，库里只存 SHA-256 摘要，一次消费，PKCE 校验 S256。
4. `/api/oauth/token` 换访问令牌与刷新令牌，同样只存 SHA-256；刷新令牌轮换，
   旧令牌作废。停用用户（`valid=0`）与缺少 `client_id` 的请求拒绝换令牌。
5. 会话放 HttpOnly Cookie（`vz_access`、`vz_refresh`），不进 localStorage。
   登出与撤销接口清 Cookie 并作废令牌。

登录限流按 `IP:用户名` 计数（超限回 `/login?error=locked`）。注意：IP 取自
`X-Forwarded-For`，无置信反代时可伪造，部署方式确认前不要依赖它做硬防护。

## 错误契约

| 情形 | HTTP | 响应体 |
|---|---|---|
| 数据库异常 | 503 | `message`：数据库不可用 |
| 其它服务端异常 | 500 | `message`：服务端错误 |
| 业务错误（<500） | 原样透传 | 原样 |
| 未认证（页面） | 跳转 `/login` | — |

堆栈只写服务端日志，不进响应。错误文案放 `message` 而不是 `statusMessage`——
h3 会把 `statusMessage` 里的非 ASCII 字符剥掉，中文文案必须走 `message`。

## 口令与摘要口径

| 用途 | 算法 | 落库 |
|---|---|---|
| 登录口令 | scrypt（N=2^17，r=8，p=1） | `t_sys_user.password_hash` |
| 活动准入口令 | SM3 | `t_e3dp_campaign.access_sm3`，64 位十六进制 |
| 授权码 / 访问令牌 / 刷新令牌 | SHA-256 | `t_sys_oauth_code.code_hash` 等 |
| 联系方式 | SM4 密文 + 脱敏列 | `contact_encrypt` / `contact_mask` |
