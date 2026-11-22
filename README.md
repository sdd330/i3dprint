# Violet Print

TEAM 6940 校园三维打印。Nuxt SSR 读取 MySQL，登录走 OAuth 2.1。

## 文档

- [docs/README.md](docs/README.md)：文档索引
- [docs/architecture.md](docs/architecture.md)：技术栈、SSR 数据流、鉴权、错误契约
- [docs/database-design.md](docs/database-design.md)：命名、类型、状态字典、表清单
- [docs/api.md](docs/api.md)：路由与鉴权矩阵
- [docs/development.md](docs/development.md)：命令、环境变量、格式化、已知问题

## 目录

- [apps/web](apps/web)：Nuxt SSR（唯一包）
- [db/e3dp_schema.sql](db/e3dp_schema.sql)：建表脚本，库名 `i3dprint`

## 使用

```bash
pnpm install
pnpm dev        # 开发
pnpm build      # 构建
pnpm lint       # 检查
```

## 许可

[MIT](LICENSE)
