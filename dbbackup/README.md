# 数据库快照

`e3dp.db` 是本地 SQLite 数据库的时间点快照，随仓库一起版本化，用于回滚与交接。

- **来源**：`app/backend/data/e3dp.db`
- **快照时间**：2026-11-22
- **内容**：20 张表；当前为空库状态（`orders` / `print_jobs` / `reviews` / `cost_ledger` / `models` / `model_versions` 均为 0 行），保留配置类数据（活动模板、当前活动参数、站娘知识库 11 条、教材切块 108 块、软件设置 26 项）与审计日志 27 条
- **规模**：3.3 MB

## 恢复方式

```bash
cp dbbackup/e3dp.db app/backend/data/e3dp.db
```

覆盖前建议先停服务，否则可能有未落盘的 WAL 变更。

## 注意

库内 `campaigns.password` 是**明文**的活动口令，而它现在是学生登录的准入门槛。如果本仓库是公开的，推送前应先轮换口令（登录后在「活动管理」里改），否则等于公开凭证。

`app_settings` 里的 API Key 是通过 Fernet 加密存储的，密钥派生自 `JWT_SECRET`——换过 `JWT_SECRET` 的环境解不开这些密文，需要在「软件设置」重新录入。
