# 活动配置云端参考

从本地 SQLite 导出的活动配置副本，供云端部署时参照/导入。**导出于 2026-11-22 09:27**。

## 文件

| 文件 | 来源 | 用途 |
|---|---|---|
| `campaign-config.json` | `campaigns.config`（活动 id=1） | 当前活动生效的参数副本，可直接灌进云端 `campaigns.config` |
| `template-config.json` | `config_templates.data`（`is_default=1`） | 全局默认模板，新建活动时的继承基线，可灌进 `config_templates.data` |

两个文件都是纯 JSON，键结构与线上一致（8 个配置分类 + 活动副本里的 `_sources` 继承来源标记）。

## 来源活动

| 字段 | 值 |
|---|---|
| id | 1 |
| 名称 | 2026 秋季第 1 场 · 3D 打印体验活动 |
| 状态 | 开放中 |
| 开放 / 收尾 | 2026-08-28 09:00 / 2026-08-29 18:00 |
| 人数上限 | 20 |

## 与模板的差异

活动副本大部分沿用模板，仅 3 处自定义（`_sources` 里 6 个分类标 `custom` 是历史编辑留下的标记，实际内容相同）：

| 分类 | 差异 |
|---|---|
| `compliance` | `pickup_location`、`pickup_window` 不同 |
| `fee` | `materials` 不同（活动里只保留 PLA 白色一种有货颜色） |
| `print` | `printers` 不同（设备清单） |

## 导入云端的方式

### 方式 A：直接灌库（换库迁移时最省事）

```sql
-- 活动参数副本
UPDATE campaigns SET config = '<campaign-config.json 的完整内容>' WHERE id = 1;
-- 默认模板
UPDATE config_templates SET data = '<template-config.json 的完整内容>' WHERE is_default = 1;
```

或用脚本读文件后 `json.dumps` 写入，避免手工拼接引号出错。

### 方式 B：界面逐项填

云端起来后，用 root/admin 登录 → **配置中心**，按分类粘贴/填写；再在**活动管理**里核对设备清单与取件信息。适合改动量小的情况。

### 方式 C：作为新活动的继承源

云端建新活动时选「继承默认模板」，模板内容即 `template-config.json`；再按场次覆盖差异项。

## 注意

- **不含活动口令**。`campaigns.password` 是独立字段，且已改为随机生成（形如 `K7MQ-XT9P`），线上值请在「活动管理」查看，不要写进仓库。
- **不含个人信息**。`compliance.contacts` 为空数组；负责人联系方式目前未入库。
- **不含 API Key**。DeepSeek / Tripo / LLM 的 Key 存在 `app_settings` 表里，是 Fernet 加密的，密钥派生自 `JWT_SECRET`。上云换 `JWT_SECRET` 后旧密文解不开，需在「软件设置」重新录入（详见《上云问题清单》P2-2）。
- 配置里的打印机（`print.printers`）是局域网设备。云端服务器访问不到校园内的 X1-Carbon，真机执行仍需要运行在校园网内的那台机器。

## 重新导出

数据有变化时重跑（在仓库根目录）：

```bash
sqlite3 app/backend/data/e3dp.db "select config from campaigns where id=1;" > /tmp/c.json
sqlite3 app/backend/data/e3dp.db "select data from config_templates where is_default=1;" > /tmp/t.json
python3 -c "import json;print(json.dumps(json.load(open('/tmp/c.json')),ensure_ascii=False,indent=2))" \
  > app/deploy/cloud-reference/campaign-config.json
python3 -c "import json;print(json.dumps(json.load(open('/tmp/t.json')),ensure_ascii=False,indent=2))" \
  > app/deploy/cloud-reference/template-config.json
```
