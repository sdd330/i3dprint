# Database Design

建表脚本：[db/e3dp_schema.sql](../db/e3dp_schema.sql)。

库名 `i3dprint`，字符集 `utf8mb4`，排序规则 `utf8mb4_0900_ai_ci`，引擎 InnoDB。

## 技术栈

| 层 | 选型 | 版本 |
|---|---|---|
| 包管理 | pnpm workspace | 12.21 |
| 框架 | Nuxt SSR | 4.6 |
| 构建 | Vite，Rolldown + Oxc | 8.3 |
| 语言 | TypeScript | 7.0 |
| 检查与格式 | Oxlint、Oxfmt | 1.94 / 0.79 |
| 界面 | Vue、Vue Router | 3.5 / 5 |
| 状态 | Pinia | 4.1 |
| 样式 | UnoCSS，presetWind4 | 66 |
| PWA | @vite-pwa/nuxt：可安装、autoUpdate、离线回退、maskable 图标、安装与更新提示 | 2.0 |
| 数据 | MySQL 8，服务端 `mysql2` | — |
| 访问控制 | OAuth 2.1 授权码 + PKCE S256，刷新令牌轮换 | — |

页面在服务端用 `useFetch` 请求 Nitro 接口，接口经 `~/.mysql_env` 取 `MYSQL_HOST`、`MYSQL_PORT`、`MYSQL_USER`（或 `MYSQL_ROOT`）、`MYSQL_PASSWORD`，库名 `i3dprint`。口令不进仓库。

登录口令使用 scrypt（N=2^17，r=8，p=1）写入 `t_sys_user.password_hash`。授权码、访问令牌、刷新令牌只存 SHA-256。会话放在 HttpOnly Cookie，不进 localStorage。公开客户端 `violet-z`，回调路径 `/oauth/callback`。

## 命名与必须字段

表名 `t_` + 业务名。主键 `id bigint(11) AUTO_INCREMENT`。

每张表都有：

| 字段 | 类型 | 说明 |
|---|---|---|
| `{业务名}_code` | `varchar(32)` | 唯一约束，索引名 `unique_{业务名}_code` |
| `remark` | `varchar(300)` | 备注 |
| `create_user_code` / `create_user_name` / `create_date` | `varchar(32)` / `varchar(50)` / `datetime` | 创建人与创建时间 |
| `modified_user_code` / `modified_user_name` / `modified_date` | 同上 | 修改人与修改时间，`modified_date` 自动更新 |
| `version` | `int(11)` | 乐观锁，默认 1 |
| `valid` | `tinyint(1)` | 1 有效，0 无效 |

业务主数据用 `valid=0` 做逻辑删除。外键不写 `ON DELETE CASCADE`。费用流水、用量、配置审计、操作日志保留 `valid`，只作冲正或更正标记。

`{业务名}_code`、文件名、设置键使用 `utf8mb4_0900_as_cs`，区分大小写。业务编号以 `_no` 结尾，不占用 `_code`。

审核人、配置操作人、审计操作人记在创建人字段，不再单列姓名快照。模型文件版本号是 `file_version`，与乐观锁 `version` 分开。

## 类型

| 类别 | 类型 |
|---|---|
| code | `varchar(32)` |
| 名字 | `varchar(50)` |
| 描述、超过 50 字的名称与路径 | `varchar(300)` |
| 更长正文 | `text` |
| 状态、类型、次数、重量 | `int(11)` |
| 布尔、有效性 | `tinyint(1)` |
| 主键、外键、金额、点数 | `bigint(11)` |
| 结构化快照、向量 | `json` |
| SM3、SHA-256 | `varchar(64)`，64 位十六进制 |

禁止 `float` / `double`。`json` 与 `text` 不写字面量默认值。未设置的业务时间用 `NULL`。

金额单位为分。Tripo 点数单位为万分之一点。token 单价单位为 1e-8 元。重量单位为毫克。

登录口令与活动准入口令存 SM3 摘要，不明文。联系方式存 SM4 密文 `contact_encrypt`，另有脱敏列 `contact_mask`。设置项里的 secret 只存密文或 KMS 引用。

`t_e3dp_config_audit.category` 保持 `varchar(32)`，参数分类是开放短码，没有固定枚举。

## 状态与类型字典

整型可追加，不改表结构，不用 `ENUM`。

| 字段 | 取值 |
|---|---|
| 活动状态 | 1 待开放，2 开放中，3 收尾中，4 已归档 |
| 模型来源 | 1 preset，2 upload，3 ai |
| 订单状态 | 1 draft；已暂缓旧值 2 val1_appeal，3 slicing，4 val2_pending，5 val2_failed |
| 打印状态 | 1 queued，2 printing，3 done，4 failed，5 blocked |
| 审核阶段 | 1 val1，2 val2，3 val3 |
| 审核结论 | 1 通过，2 标记，3 失败 |
| 问题阶段 | 1 val2，2 val3 |
| 问题类型 | 1 PARAMETER，2 MACHINE，3 MODEL，4 MACHINE_LIMIT，5 CONTENT，6 OTHER |
| 问题状态 | 1 open，2 resolved |
| 费用类型 | 1 filament，2 maintenance，3 api |
| 用量类型 | 1 ai_modeling，2 qa |
| 服务 | 1 tripo，2 deepseek |
| 工单状态 | 1 open，2 answered，3 closed |
| 配置范围 | 1 template，2 campaign |
| 设置分类 | 1 service，2 slicer，3 external，4 misc |
| 设置值类型 | 1 str，2 int，3 float，4 bool，5 secret |

`t_e3dp_order.filament_approved` 仍是三态：`NULL` 未检验，1 通过，0 不通过。

## 表

| 表 | 说明 |
|---|---|
| `t_sys_role` | 角色。`sys_role_code` 取值 root、admin、student |
| `t_sys_user` | 用户。`sys_user_code` 为登录名，口令为 scrypt 摘要 |
| `t_sys_oauth_client` | OAuth 客户端 |
| `t_sys_oauth_code` | 授权码，只存 SHA-256 |
| `t_sys_oauth_token` | 访问令牌与刷新令牌，只存 SHA-256 |
| `t_e3dp_campaign` | 活动配置副本 |
| `t_e3dp_model` | 模型。文件本体不在库中 |
| `t_e3dp_model_version` | 模型版本，只追加。`(model_id, file_version)` 唯一 |
| `t_e3dp_order` | 打印需求 |
| `t_e3dp_print_job` | 打印任务。`(order_id, print_seq)` 唯一 |
| `t_e3dp_review` | 审核记录 |
| `t_e3dp_issue` | 问题记录，与订单状态解耦 |
| `t_e3dp_cost_ledger` | 费用流水，只追加 |
| `t_e3dp_api_usage` | API 用量 |
| `t_e3dp_qa_ticket` | 问答工单 |
| `t_e3dp_qa_ticket_comment` | 工单回复 |
| `t_e3dp_qa_knowledge` | 站娘知识库条目 |
| `t_e3dp_kb_source` | 知识库文档。文件名唯一且区分大小写 |
| `t_e3dp_kb_chunk` | 知识库切块。`(source_id, chunk_ordinal)` 唯一 |
| `t_e3dp_config_template` | 默认活动模板 |
| `t_e3dp_config_audit` | 配置修改记录。`target_id` 不建外键 |
| `t_e3dp_audit_log` | 操作日志 |
| `t_e3dp_app_setting` | 全局设置。`setting_key` 唯一 |

外键：用户属于角色；模型属于用户；模型版本属于模型；订单属于活动、用户、模型及模型版本；打印任务、审核、问题、费用流水属于订单；费用流水可属打印任务；用量、工单、审计日志属于用户；回复属于工单；切块属于文档。
