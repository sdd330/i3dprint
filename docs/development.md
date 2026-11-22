# 开发

## 命令

在仓库根执行（pnpm workspace）：

| 命令 | 作用 |
|---|---|
| `pnpm dev` | 开发服务器（Nuxt） |
| `pnpm build` | 生产构建 |
| `pnpm lint` | oxlint |
| `pnpm fmt` | oxfmt 写入 |
| `pnpm --filter @i3dprint/web typecheck` | 类型检查（`tsc --noEmit --runExternalCode`） |
| `pnpm --filter @i3dprint/web seed:root` | 写入 root 账号与 OAuth 客户端（需 `SEED_PASSWORD`） |

## 类型检查：TS 7.1 Content Mappers（2026 实践）

本项目**不用 vue-tsc**。vue-tsc 靠打 JS 版 tsc 补丁接入 Volar，TypeScript 7 是 Go 原生
重写，没有可打补丁的 JS 入口，永久不兼容（`ERR_PACKAGE_PATH_NOT_EXPORTED`，上游
vuejs/language-tools#5381）。上游路线图明确：content mapper 落地后 vue-tsc 退场。

正解是 TypeScript 7.1 的 **content mappers** 插件点：

- `apps/web/tsconfig.json` 顶层注册 `@vue/content-mapper`（与 `compilerOptions` 平级），
  `.vue` 文件由 `tsc` 本体经 mapper 直查，SFC 的 script 与 template 都覆盖
- `tsc` 必须带 `--runExternalCode`（mapper 是 tsc 执行的 npm 包，缺了报 TS18068）
- 报错的 文件:行:列 与 vue-tsc 一致（同一套 Volar 代码生成，只是换了官方入口）

## 环境变量

MySQL 连接信息读 `~/.mysql_env`（`nuxt.config.ts` 启动时解析，`export K=V` 或 `K=V` 行格式）：

| 变量 | 说明 |
|---|---|
| `MYSQL_HOST` / `MYSQL_PORT` | 主机与端口 |
| `MYSQL_USER`（或 `MYSQL_ROOT`） | 用户 |
| `MYSQL_PASSWORD` | 口令 |
| `MYSQL_DATABASE` | 库名，缺省 `i3dprint` |

`seed:root` 另需 `SEED_PASSWORD`。口令与连接串不进仓库。

## 格式化

`.oxfmtrc.json` 钉死 `singleQuote: true`、`semi: false`、`printWidth: 150`（对齐存量风格）。
oxfmt 配置键名是 `singleQuote`/`semi`（Prettier 系），不是 `quotes`/`quoteStyle`——写错键会被静默忽略。

## 已知问题

- `nuxt typecheck`（vue-tsc 线）在 TS 7 下不可用，统一走 `tsc --runExternalCode`
- 登录限流依赖 `X-Forwarded-For`，无置信反代时可伪造；部署形态确认前不做硬防护承诺
