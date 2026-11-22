SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS i3dprint
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

ALTER DATABASE i3dprint
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE i3dprint;

-- ---------------------------------------------------------------------------
-- 系统与权限
-- ---------------------------------------------------------------------------

CREATE TABLE `t_sys_role` (
  `id` bigint(11) NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `sys_role_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '唯一约束code',
  `name` varchar(50) NOT NULL COMMENT '角色显示名',
  `permissions` json NOT NULL COMMENT '权限点数组，如 order:create；由应用写入',
  `builtin` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否内置角色：1 内置不可删除，0 可删除',
  `remark` varchar(300) DEFAULT NULL COMMENT '备注',
  `create_user_code` varchar(32) DEFAULT NULL COMMENT '创建人code',
  `create_user_name` varchar(50) DEFAULT NULL COMMENT '创建人',
  `create_date` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建日期',
  `modified_user_code` varchar(32) DEFAULT NULL COMMENT '修改人code',
  `modified_user_name` varchar(50) DEFAULT NULL COMMENT '修改人',
  `modified_date` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `version` int(11) DEFAULT '1' COMMENT '版本号（乐观锁）',
  `valid` tinyint(1) DEFAULT '1' COMMENT '数据有效性：1=有效；0=无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_sys_role_code` (`sys_role_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC COMMENT='系统与权限-角色，sys_role_code 取值 root、admin、student';

CREATE TABLE `t_sys_user` (
  `id` bigint(11) NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `sys_user_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '唯一约束code',
  `name` varchar(50) NOT NULL COMMENT '真实姓名',
  `grade` varchar(50) NOT NULL DEFAULT '' COMMENT '年级或班级',
  `contact_encrypt` varchar(300) DEFAULT NULL COMMENT '联系方式 SM4 密文',
  `contact_mask` varchar(50) DEFAULT NULL COMMENT '联系方式脱敏展示',
  `password_hash` varchar(255) NOT NULL COMMENT '登录口令 scrypt 摘要，不可逆，不明文',
  `role_id` bigint(11) NOT NULL COMMENT '所属角色',
  `is_active` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否启用：1 启用，0 停用',
  `remark` varchar(300) DEFAULT NULL COMMENT '备注',
  `create_user_code` varchar(32) DEFAULT NULL COMMENT '创建人code',
  `create_user_name` varchar(50) DEFAULT NULL COMMENT '创建人',
  `create_date` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建日期',
  `modified_user_code` varchar(32) DEFAULT NULL COMMENT '修改人code',
  `modified_user_name` varchar(50) DEFAULT NULL COMMENT '修改人',
  `modified_date` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `version` int(11) DEFAULT '1' COMMENT '版本号（乐观锁）',
  `valid` tinyint(1) DEFAULT '1' COMMENT '数据有效性：1=有效；0=无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_sys_user_code` (`sys_user_code`),
  KEY `idx_sys_user_role_id` (`role_id`),
  CONSTRAINT `fk_sys_user_role_id` FOREIGN KEY (`role_id`) REFERENCES `t_sys_role` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC COMMENT='系统与权限-用户，sys_user_code 为登录名';

CREATE TABLE `t_sys_oauth_client` (
  `id` bigint(11) NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `sys_oauth_client_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '唯一约束code',
  `name` varchar(50) NOT NULL COMMENT '客户端名称',
  `redirect_path` varchar(300) NOT NULL COMMENT '允许的回调路径',
  `remark` varchar(300) DEFAULT NULL COMMENT '备注',
  `create_user_code` varchar(32) DEFAULT NULL COMMENT '创建人code',
  `create_user_name` varchar(50) DEFAULT NULL COMMENT '创建人',
  `create_date` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建日期',
  `modified_user_code` varchar(32) DEFAULT NULL COMMENT '修改人code',
  `modified_user_name` varchar(50) DEFAULT NULL COMMENT '修改人',
  `modified_date` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `version` int(11) DEFAULT '1' COMMENT '版本号（乐观锁）',
  `valid` tinyint(1) DEFAULT '1' COMMENT '数据有效性：1=有效；0=无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_sys_oauth_client_code` (`sys_oauth_client_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC COMMENT='系统与权限-OAuth 客户端，公开客户端，强制 PKCE S256';

CREATE TABLE `t_sys_oauth_code` (
  `id` bigint(11) NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `sys_oauth_code_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '唯一约束code',
  `code_hash` varchar(64) NOT NULL COMMENT '授权码 SHA-256',
  `client_id` bigint(11) NOT NULL COMMENT '所属客户端',
  `user_id` bigint(11) NOT NULL COMMENT '授权用户',
  `redirect_uri` varchar(300) NOT NULL COMMENT '本次回调地址',
  `code_challenge` varchar(128) NOT NULL COMMENT 'PKCE S256 challenge',
  `scope` varchar(300) NOT NULL COMMENT '授权范围',
  `expires_at` datetime NOT NULL COMMENT '过期时间',
  `consumed` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否已兑换：1 是，0 否',
  `remark` varchar(300) DEFAULT NULL COMMENT '备注',
  `create_user_code` varchar(32) DEFAULT NULL COMMENT '创建人code',
  `create_user_name` varchar(50) DEFAULT NULL COMMENT '创建人',
  `create_date` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建日期',
  `modified_user_code` varchar(32) DEFAULT NULL COMMENT '修改人code',
  `modified_user_name` varchar(50) DEFAULT NULL COMMENT '修改人',
  `modified_date` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `version` int(11) DEFAULT '1' COMMENT '版本号（乐观锁）',
  `valid` tinyint(1) DEFAULT '1' COMMENT '数据有效性：1=有效；0=无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_sys_oauth_code_code` (`sys_oauth_code_code`),
  UNIQUE KEY `unique_sys_oauth_code_hash` (`code_hash`),
  KEY `idx_sys_oauth_code_client_id` (`client_id`),
  KEY `idx_sys_oauth_code_user_id` (`user_id`),
  CONSTRAINT `fk_sys_oauth_code_client_id` FOREIGN KEY (`client_id`) REFERENCES `t_sys_oauth_client` (`id`),
  CONSTRAINT `fk_sys_oauth_code_user_id` FOREIGN KEY (`user_id`) REFERENCES `t_sys_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC COMMENT='系统与权限-OAuth 授权码';

CREATE TABLE `t_sys_oauth_token` (
  `id` bigint(11) NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `sys_oauth_token_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '唯一约束code',
  `user_id` bigint(11) NOT NULL COMMENT '授权用户',
  `client_id` bigint(11) NOT NULL COMMENT '所属客户端',
  `access_hash` varchar(64) NOT NULL COMMENT '访问令牌 SHA-256',
  `refresh_hash` varchar(64) NOT NULL COMMENT '刷新令牌 SHA-256',
  `scope` varchar(300) NOT NULL COMMENT '授权范围',
  `access_expires` datetime NOT NULL COMMENT '访问令牌过期时间',
  `refresh_expires` datetime NOT NULL COMMENT '刷新令牌过期时间',
  `remark` varchar(300) DEFAULT NULL COMMENT '备注',
  `create_user_code` varchar(32) DEFAULT NULL COMMENT '创建人code',
  `create_user_name` varchar(50) DEFAULT NULL COMMENT '创建人',
  `create_date` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建日期',
  `modified_user_code` varchar(32) DEFAULT NULL COMMENT '修改人code',
  `modified_user_name` varchar(50) DEFAULT NULL COMMENT '修改人',
  `modified_date` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `version` int(11) DEFAULT '1' COMMENT '版本号（乐观锁）',
  `valid` tinyint(1) DEFAULT '1' COMMENT '数据有效性：1=有效；0=无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_sys_oauth_token_code` (`sys_oauth_token_code`),
  UNIQUE KEY `unique_sys_oauth_token_access` (`access_hash`),
  UNIQUE KEY `unique_sys_oauth_token_refresh` (`refresh_hash`),
  KEY `idx_sys_oauth_token_user_id` (`user_id`),
  KEY `idx_sys_oauth_token_client_id` (`client_id`),
  CONSTRAINT `fk_sys_oauth_token_user_id` FOREIGN KEY (`user_id`) REFERENCES `t_sys_user` (`id`),
  CONSTRAINT `fk_sys_oauth_token_client_id` FOREIGN KEY (`client_id`) REFERENCES `t_sys_oauth_client` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC COMMENT='系统与权限-OAuth 令牌，只存摘要';

-- ---------------------------------------------------------------------------
-- 活动与模型
-- ---------------------------------------------------------------------------

CREATE TABLE `t_e3dp_campaign` (
  `id` bigint(11) NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `e3dp_campaign_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '唯一约束code',
  `name` varchar(300) NOT NULL COMMENT '活动名称',
  `status` int(11) NOT NULL DEFAULT '1' COMMENT '活动状态：1 待开放，2 开放中，3 收尾中，4 已归档',
  `access_sm3` varchar(64) NOT NULL COMMENT '活动准入口令 SM3 摘要，64 位十六进制，不明文',
  `open_date` datetime DEFAULT NULL COMMENT '开放时间，未设置为空',
  `close_date` datetime DEFAULT NULL COMMENT '截止时间，未设置为空',
  `max_participants` int(11) NOT NULL DEFAULT '20' COMMENT '人数上限',
  `config` json NOT NULL COMMENT '活动参数副本，金额单位分；由应用写入',
  `bill` json DEFAULT NULL COMMENT '活动账单快照，金额单位分，归档时生成',
  `archive_date` datetime DEFAULT NULL COMMENT '归档时间，未归档为空',
  `remark` varchar(300) DEFAULT NULL COMMENT '备注',
  `create_user_code` varchar(32) DEFAULT NULL COMMENT '创建人code',
  `create_user_name` varchar(50) DEFAULT NULL COMMENT '创建人',
  `create_date` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建日期',
  `modified_user_code` varchar(32) DEFAULT NULL COMMENT '修改人code',
  `modified_user_name` varchar(50) DEFAULT NULL COMMENT '修改人',
  `modified_date` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `version` int(11) DEFAULT '1' COMMENT '版本号（乐观锁）',
  `valid` tinyint(1) DEFAULT '1' COMMENT '数据有效性：1=有效；0=无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_e3dp_campaign_code` (`e3dp_campaign_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC COMMENT='打印业务-活动，保存配置副本';

CREATE TABLE `t_e3dp_model` (
  `id` bigint(11) NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `e3dp_model_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '唯一约束code',
  `owner_id` bigint(11) DEFAULT NULL COMMENT '归属用户，预设模型可空',
  `name` varchar(300) NOT NULL COMMENT '模型名',
  `description` text NOT NULL COMMENT '模型描述',
  `kind` int(11) NOT NULL DEFAULT '2' COMMENT '来源：1 preset，2 upload，3 ai',
  `remark` varchar(300) DEFAULT NULL COMMENT '备注',
  `create_user_code` varchar(32) DEFAULT NULL COMMENT '创建人code',
  `create_user_name` varchar(50) DEFAULT NULL COMMENT '创建人',
  `create_date` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建日期',
  `modified_user_code` varchar(32) DEFAULT NULL COMMENT '修改人code',
  `modified_user_name` varchar(50) DEFAULT NULL COMMENT '修改人',
  `modified_date` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `version` int(11) DEFAULT '1' COMMENT '版本号（乐观锁）',
  `valid` tinyint(1) DEFAULT '1' COMMENT '数据有效性：1=有效；0=无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_e3dp_model_code` (`e3dp_model_code`),
  KEY `idx_e3dp_model_owner_id` (`owner_id`),
  CONSTRAINT `fk_e3dp_model_owner_id` FOREIGN KEY (`owner_id`) REFERENCES `t_sys_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC COMMENT='打印业务-模型，文件本体不在库中';

CREATE TABLE `t_e3dp_model_version` (
  `id` bigint(11) NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `e3dp_model_version_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '唯一约束code',
  `model_id` bigint(11) NOT NULL COMMENT '所属模型',
  `file_version` int(11) NOT NULL DEFAULT '1' COMMENT '文件版本号，同一模型内递增',
  `file_path` varchar(300) NOT NULL DEFAULT '' COMMENT '模型文件路径或对象存储键',
  `file_hash` varchar(64) NOT NULL DEFAULT '' COMMENT '文件 SHA-256，64 位十六进制',
  `stats` json NOT NULL COMMENT '几何分析，含体积、表面积、包围盒；由应用写入',
  `checks` json NOT NULL COMMENT '检查结果，含封闭、流形、自交、壁厚、悬垂；由应用写入',
  `remark` varchar(300) DEFAULT NULL COMMENT '备注',
  `create_user_code` varchar(32) DEFAULT NULL COMMENT '创建人code',
  `create_user_name` varchar(50) DEFAULT NULL COMMENT '创建人',
  `create_date` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建日期',
  `modified_user_code` varchar(32) DEFAULT NULL COMMENT '修改人code',
  `modified_user_name` varchar(50) DEFAULT NULL COMMENT '修改人',
  `modified_date` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `version` int(11) DEFAULT '1' COMMENT '版本号（乐观锁）',
  `valid` tinyint(1) DEFAULT '1' COMMENT '数据有效性：1=有效；0=无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_e3dp_model_version_code` (`e3dp_model_version_code`),
  UNIQUE KEY `unique_e3dp_model_file_version` (`model_id`, `file_version`),
  CONSTRAINT `fk_e3dp_model_version_model_id` FOREIGN KEY (`model_id`) REFERENCES `t_e3dp_model` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC COMMENT='打印业务-模型版本，只追加不覆盖';

-- ---------------------------------------------------------------------------
-- 打印需求与任务
-- ---------------------------------------------------------------------------

CREATE TABLE `t_e3dp_order` (
  `id` bigint(11) NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `e3dp_order_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '唯一约束code',
  `campaign_id` bigint(11) NOT NULL COMMENT '所属活动',
  `user_id` bigint(11) NOT NULL COMMENT '下单学生',
  `model_id` bigint(11) DEFAULT NULL COMMENT '关联模型，未关联为空',
  `model_version_id` bigint(11) DEFAULT NULL COMMENT '关联的模型版本，未关联为空',
  `name` varchar(300) NOT NULL DEFAULT '新打印需求' COMMENT '需求名称',
  `status` int(11) NOT NULL DEFAULT '1' COMMENT '订单状态：1 draft；已暂缓旧值 2 val1_appeal，3 slicing，4 val2_pending，5 val2_failed',
  `placement` json DEFAULT NULL COMMENT '摆放、朝向与缩放，传递给切片',
  `geometry` json DEFAULT NULL COMMENT '几何分析报告与服务端校验结果',
  `material_no` varchar(32) NOT NULL DEFAULT 'pla' COMMENT '耗材编号',
  `color` varchar(32) NOT NULL DEFAULT '#E8602C' COMMENT '颜色，十六进制串',
  `params` json DEFAULT NULL COMMENT '打印参数，含强度、层高与进阶项',
  `val1` json DEFAULT NULL COMMENT 'Val1 质量关卡快照，含标记与人工复核结论',
  `slice` json DEFAULT NULL COMMENT '切片结果快照，旧流程保留',
  `val2auto` json DEFAULT NULL COMMENT 'Val2 自动核验快照，旧流程保留',
  `appeal` json DEFAULT NULL COMMENT '申诉信息，旧流程保留',
  `self_filament` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否自备耗材：1 是，0 否',
  `filament_approved` tinyint(1) DEFAULT NULL COMMENT '自备耗材检验：NULL 未检验，1 通过，0 不通过',
  `filament_note` text NOT NULL COMMENT '耗材检验备注',
  `cost` json NOT NULL COMMENT '成本明细快照，金额单位分；由应用写入',
  `reprint_rate` json NOT NULL COMMENT '设备问题半价重打的责任分摊；由应用写入',
  `feedback` json DEFAULT NULL COMMENT '用户反馈',
  `timeline` json NOT NULL COMMENT '状态时间轴，只追加记录；由应用写入',
  `remark` varchar(300) DEFAULT NULL COMMENT '备注',
  `create_user_code` varchar(32) DEFAULT NULL COMMENT '创建人code',
  `create_user_name` varchar(50) DEFAULT NULL COMMENT '创建人',
  `create_date` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建日期',
  `modified_user_code` varchar(32) DEFAULT NULL COMMENT '修改人code',
  `modified_user_name` varchar(50) DEFAULT NULL COMMENT '修改人',
  `modified_date` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `version` int(11) DEFAULT '1' COMMENT '版本号（乐观锁）',
  `valid` tinyint(1) DEFAULT '1' COMMENT '数据有效性：1=有效；0=无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_e3dp_order_code` (`e3dp_order_code`),
  KEY `idx_e3dp_order_campaign_status` (`campaign_id`, `status`),
  KEY `idx_e3dp_order_user_id` (`user_id`),
  KEY `idx_e3dp_order_status` (`status`),
  KEY `idx_e3dp_order_model_id` (`model_id`),
  KEY `idx_e3dp_order_model_version_id` (`model_version_id`),
  CONSTRAINT `fk_e3dp_order_campaign_id` FOREIGN KEY (`campaign_id`) REFERENCES `t_e3dp_campaign` (`id`),
  CONSTRAINT `fk_e3dp_order_user_id` FOREIGN KEY (`user_id`) REFERENCES `t_sys_user` (`id`),
  CONSTRAINT `fk_e3dp_order_model_id` FOREIGN KEY (`model_id`) REFERENCES `t_e3dp_model` (`id`),
  CONSTRAINT `fk_e3dp_order_model_version_id` FOREIGN KEY (`model_version_id`) REFERENCES `t_e3dp_model_version` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC COMMENT='打印业务-打印需求';

CREATE TABLE `t_e3dp_print_job` (
  `id` bigint(11) NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `e3dp_print_job_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '唯一约束code',
  `order_id` bigint(11) NOT NULL COMMENT '所属需求',
  `print_seq` int(11) NOT NULL DEFAULT '1' COMMENT '第几次打印，同一需求内不可重复',
  `printer_no` varchar(32) DEFAULT NULL COMMENT '打印机编号，如 x1c-01，未分配为空',
  `status` int(11) NOT NULL DEFAULT '1' COMMENT '打印状态：1 queued，2 printing，3 done，4 failed，5 blocked',
  `est_time_sec` int(11) NOT NULL DEFAULT '0' COMMENT '预估耗时，单位秒',
  `est_weight` int(11) NOT NULL DEFAULT '0' COMMENT '预估重量，单位毫克',
  `actual_weight` int(11) DEFAULT NULL COMMENT '实际重量，单位毫克，未称重为空',
  `gcode` json NOT NULL COMMENT '切片或 G-code 元信息；由应用写入',
  `start_date` datetime DEFAULT NULL COMMENT '开始打印时间，未开始为空',
  `end_date` datetime DEFAULT NULL COMMENT '结束时间，未结束为空',
  `note` text NOT NULL COMMENT '打印备注，含异常与人工时间说明',
  `remark` varchar(300) DEFAULT NULL COMMENT '备注',
  `create_user_code` varchar(32) DEFAULT NULL COMMENT '创建人code',
  `create_user_name` varchar(50) DEFAULT NULL COMMENT '创建人',
  `create_date` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建日期',
  `modified_user_code` varchar(32) DEFAULT NULL COMMENT '修改人code',
  `modified_user_name` varchar(50) DEFAULT NULL COMMENT '修改人',
  `modified_date` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `version` int(11) DEFAULT '1' COMMENT '版本号（乐观锁）',
  `valid` tinyint(1) DEFAULT '1' COMMENT '数据有效性：1=有效；0=无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_e3dp_print_job_code` (`e3dp_print_job_code`),
  UNIQUE KEY `unique_e3dp_print_job_seq` (`order_id`, `print_seq`),
  KEY `idx_e3dp_print_job_status` (`status`),
  CONSTRAINT `fk_e3dp_print_job_order_id` FOREIGN KEY (`order_id`) REFERENCES `t_e3dp_order` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC COMMENT='打印业务-打印任务，一个需求可多次打印';

-- ---------------------------------------------------------------------------
-- 审核、问题与费用
-- ---------------------------------------------------------------------------

CREATE TABLE `t_e3dp_review` (
  `id` bigint(11) NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `e3dp_review_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '唯一约束code',
  `order_id` bigint(11) NOT NULL COMMENT '所属需求',
  `stage` int(11) NOT NULL COMMENT '审核阶段：1 val1，2 val2，3 val3',
  `result` int(11) NOT NULL COMMENT '审核结论：1 通过，2 标记，3 失败',
  `note` text NOT NULL COMMENT '审核备注',
  `remark` varchar(300) DEFAULT NULL COMMENT '备注',
  `create_user_code` varchar(32) DEFAULT NULL COMMENT '创建人code',
  `create_user_name` varchar(50) DEFAULT NULL COMMENT '创建人',
  `create_date` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建日期',
  `modified_user_code` varchar(32) DEFAULT NULL COMMENT '修改人code',
  `modified_user_name` varchar(50) DEFAULT NULL COMMENT '修改人',
  `modified_date` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `version` int(11) DEFAULT '1' COMMENT '版本号（乐观锁）',
  `valid` tinyint(1) DEFAULT '1' COMMENT '数据有效性：1=有效；0=无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_e3dp_review_code` (`e3dp_review_code`),
  KEY `idx_e3dp_review_order_id` (`order_id`),
  CONSTRAINT `fk_e3dp_review_order_id` FOREIGN KEY (`order_id`) REFERENCES `t_e3dp_order` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC COMMENT='打印业务-审核记录，审核人记在创建人字段';

CREATE TABLE `t_e3dp_issue` (
  `id` bigint(11) NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `e3dp_issue_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '唯一约束code',
  `order_id` bigint(11) NOT NULL COMMENT '所属需求',
  `stage` int(11) NOT NULL COMMENT '问题阶段：1 val2，2 val3',
  `issue_type` int(11) NOT NULL COMMENT '问题类型：1 PARAMETER，2 MACHINE，3 MODEL，4 MACHINE_LIMIT，5 CONTENT，6 OTHER',
  `description` text NOT NULL COMMENT '问题描述',
  `status` int(11) NOT NULL DEFAULT '1' COMMENT '问题状态：1 open，2 resolved',
  `remark` varchar(300) DEFAULT NULL COMMENT '备注',
  `create_user_code` varchar(32) DEFAULT NULL COMMENT '创建人code',
  `create_user_name` varchar(50) DEFAULT NULL COMMENT '创建人',
  `create_date` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建日期',
  `modified_user_code` varchar(32) DEFAULT NULL COMMENT '修改人code',
  `modified_user_name` varchar(50) DEFAULT NULL COMMENT '修改人',
  `modified_date` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `version` int(11) DEFAULT '1' COMMENT '版本号（乐观锁）',
  `valid` tinyint(1) DEFAULT '1' COMMENT '数据有效性：1=有效；0=无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_e3dp_issue_code` (`e3dp_issue_code`),
  KEY `idx_e3dp_issue_order_id` (`order_id`),
  CONSTRAINT `fk_e3dp_issue_order_id` FOREIGN KEY (`order_id`) REFERENCES `t_e3dp_order` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC COMMENT='打印业务-问题记录，与订单状态解耦';

CREATE TABLE `t_e3dp_cost_ledger` (
  `id` bigint(11) NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `e3dp_cost_ledger_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '唯一约束code',
  `order_id` bigint(11) DEFAULT NULL COMMENT '关联需求，活动级费用可空',
  `print_job_id` bigint(11) DEFAULT NULL COMMENT '关联打印任务，非单次打印费用可空',
  `kind` int(11) NOT NULL COMMENT '费用类型：1 filament，2 maintenance，3 api',
  `amount` bigint(11) NOT NULL COMMENT '金额，单位分',
  `reason` text NOT NULL COMMENT '计费原因',
  `remark` varchar(300) DEFAULT NULL COMMENT '备注',
  `create_user_code` varchar(32) DEFAULT NULL COMMENT '创建人code',
  `create_user_name` varchar(50) DEFAULT NULL COMMENT '创建人',
  `create_date` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建日期',
  `modified_user_code` varchar(32) DEFAULT NULL COMMENT '修改人code',
  `modified_user_name` varchar(50) DEFAULT NULL COMMENT '修改人',
  `modified_date` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `version` int(11) DEFAULT '1' COMMENT '版本号（乐观锁）',
  `valid` tinyint(1) DEFAULT '1' COMMENT '数据有效性：1=有效；0=无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_e3dp_cost_ledger_code` (`e3dp_cost_ledger_code`),
  KEY `idx_e3dp_cost_ledger_order_id` (`order_id`),
  KEY `idx_e3dp_cost_ledger_print_job_id` (`print_job_id`),
  CONSTRAINT `fk_e3dp_cost_ledger_order_id` FOREIGN KEY (`order_id`) REFERENCES `t_e3dp_order` (`id`),
  CONSTRAINT `fk_e3dp_cost_ledger_print_job_id` FOREIGN KEY (`print_job_id`) REFERENCES `t_e3dp_print_job` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC COMMENT='费用-费用流水，只追加；valid=0 仅作冲正标记';

CREATE TABLE `t_e3dp_api_usage` (
  `id` bigint(11) NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `e3dp_api_usage_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '唯一约束code',
  `kind` int(11) NOT NULL COMMENT '用量类型：1 ai_modeling，2 qa',
  `service` int(11) NOT NULL COMMENT '服务：1 tripo，2 deepseek',
  `user_id` bigint(11) DEFAULT NULL COMMENT '触发用户，系统调用可空',
  `input_tokens` int(11) NOT NULL DEFAULT '0' COMMENT '输入 token 数',
  `output_tokens` int(11) NOT NULL DEFAULT '0' COMMENT '输出 token 数',
  `points` bigint(11) NOT NULL DEFAULT '0' COMMENT 'Tripo 点数，单位为万分之一点',
  `unit_price` bigint(11) NOT NULL DEFAULT '0' COMMENT '单价，单位为 1e-8 元',
  `amount` bigint(11) NOT NULL DEFAULT '0' COMMENT '金额，单位分',
  `meta` json NOT NULL COMMENT '原始用量元数据；由应用写入',
  `remark` varchar(300) DEFAULT NULL COMMENT '备注',
  `create_user_code` varchar(32) DEFAULT NULL COMMENT '创建人code',
  `create_user_name` varchar(50) DEFAULT NULL COMMENT '创建人',
  `create_date` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建日期',
  `modified_user_code` varchar(32) DEFAULT NULL COMMENT '修改人code',
  `modified_user_name` varchar(50) DEFAULT NULL COMMENT '修改人',
  `modified_date` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `version` int(11) DEFAULT '1' COMMENT '版本号（乐观锁）',
  `valid` tinyint(1) DEFAULT '1' COMMENT '数据有效性：1=有效；0=无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_e3dp_api_usage_code` (`e3dp_api_usage_code`),
  KEY `idx_e3dp_api_usage_user_id` (`user_id`),
  CONSTRAINT `fk_e3dp_api_usage_user_id` FOREIGN KEY (`user_id`) REFERENCES `t_sys_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC COMMENT='费用-API 用量明细，按实际用量计费';

-- ---------------------------------------------------------------------------
-- 问答
-- ---------------------------------------------------------------------------

CREATE TABLE `t_e3dp_qa_ticket` (
  `id` bigint(11) NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `e3dp_qa_ticket_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '唯一约束code',
  `title` varchar(300) NOT NULL COMMENT '工单标题',
  `content` text NOT NULL COMMENT '工单正文',
  `author_id` bigint(11) DEFAULT NULL COMMENT '提问用户，匿名或用户已删除时可空',
  `author_name` varchar(50) NOT NULL DEFAULT '' COMMENT '作者名快照',
  `status` int(11) NOT NULL DEFAULT '1' COMMENT '工单状态：1 open，2 answered，3 closed',
  `remark` varchar(300) DEFAULT NULL COMMENT '备注',
  `create_user_code` varchar(32) DEFAULT NULL COMMENT '创建人code',
  `create_user_name` varchar(50) DEFAULT NULL COMMENT '创建人',
  `create_date` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建日期',
  `modified_user_code` varchar(32) DEFAULT NULL COMMENT '修改人code',
  `modified_user_name` varchar(50) DEFAULT NULL COMMENT '修改人',
  `modified_date` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `version` int(11) DEFAULT '1' COMMENT '版本号（乐观锁）',
  `valid` tinyint(1) DEFAULT '1' COMMENT '数据有效性：1=有效；0=无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_e3dp_qa_ticket_code` (`e3dp_qa_ticket_code`),
  KEY `idx_e3dp_qa_ticket_author_id` (`author_id`),
  CONSTRAINT `fk_e3dp_qa_ticket_author_id` FOREIGN KEY (`author_id`) REFERENCES `t_sys_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC COMMENT='问答-工单';

CREATE TABLE `t_e3dp_qa_ticket_comment` (
  `id` bigint(11) NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `e3dp_qa_ticket_comment_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '唯一约束code',
  `ticket_id` bigint(11) NOT NULL COMMENT '所属工单',
  `author_name` varchar(50) NOT NULL COMMENT '回复人快照',
  `content` text NOT NULL COMMENT '回复内容',
  `remark` varchar(300) DEFAULT NULL COMMENT '备注',
  `create_user_code` varchar(32) DEFAULT NULL COMMENT '创建人code',
  `create_user_name` varchar(50) DEFAULT NULL COMMENT '创建人',
  `create_date` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建日期',
  `modified_user_code` varchar(32) DEFAULT NULL COMMENT '修改人code',
  `modified_user_name` varchar(50) DEFAULT NULL COMMENT '修改人',
  `modified_date` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `version` int(11) DEFAULT '1' COMMENT '版本号（乐观锁）',
  `valid` tinyint(1) DEFAULT '1' COMMENT '数据有效性：1=有效；0=无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_e3dp_qa_ticket_comment_code` (`e3dp_qa_ticket_comment_code`),
  KEY `idx_e3dp_qa_ticket_comment_ticket_id` (`ticket_id`),
  CONSTRAINT `fk_e3dp_qa_ticket_comment_ticket_id` FOREIGN KEY (`ticket_id`) REFERENCES `t_e3dp_qa_ticket` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC COMMENT='问答-工单回复';

CREATE TABLE `t_e3dp_qa_knowledge` (
  `id` bigint(11) NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `e3dp_qa_knowledge_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '唯一约束code',
  `keywords` json NOT NULL COMMENT '关键词数组，用于命中匹配；由应用写入',
  `question` varchar(300) NOT NULL DEFAULT '' COMMENT '标准问法',
  `answer` text NOT NULL COMMENT '答案文本',
  `step_context` varchar(300) NOT NULL DEFAULT '' COMMENT '步骤上下文，限定命中的流程步骤',
  `animation_key` varchar(300) NOT NULL DEFAULT '' COMMENT 'Spine 动画关键字',
  `enabled` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否启用：1 启用，0 停用',
  `remark` varchar(300) DEFAULT NULL COMMENT '备注',
  `create_user_code` varchar(32) DEFAULT NULL COMMENT '创建人code',
  `create_user_name` varchar(50) DEFAULT NULL COMMENT '创建人',
  `create_date` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建日期',
  `modified_user_code` varchar(32) DEFAULT NULL COMMENT '修改人code',
  `modified_user_name` varchar(50) DEFAULT NULL COMMENT '修改人',
  `modified_date` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `version` int(11) DEFAULT '1' COMMENT '版本号（乐观锁）',
  `valid` tinyint(1) DEFAULT '1' COMMENT '数据有效性：1=有效；0=无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_e3dp_qa_knowledge_code` (`e3dp_qa_knowledge_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC COMMENT='问答-站娘知识库条目';

-- ---------------------------------------------------------------------------
-- 知识库
-- ---------------------------------------------------------------------------

CREATE TABLE `t_e3dp_kb_source` (
  `id` bigint(11) NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `e3dp_kb_source_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '唯一约束code',
  `file_name` varchar(300) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '文件名，区分大小写',
  `file_path` varchar(300) NOT NULL DEFAULT '' COMMENT '文件路径或对象存储键',
  `file_hash` varchar(64) NOT NULL DEFAULT '' COMMENT '文件 SHA-256，64 位十六进制，用于判断是否重新切块',
  `chunk_count` int(11) NOT NULL DEFAULT '0' COMMENT '切块数量',
  `idf` json NOT NULL COMMENT '文档级 IDF 词表；由应用写入',
  `embedding_model` varchar(300) NOT NULL DEFAULT '' COMMENT '稠密索引模型，空串表示仅 TF-IDF',
  `remark` varchar(300) DEFAULT NULL COMMENT '备注',
  `create_user_code` varchar(32) DEFAULT NULL COMMENT '创建人code',
  `create_user_name` varchar(50) DEFAULT NULL COMMENT '创建人',
  `create_date` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建日期',
  `modified_user_code` varchar(32) DEFAULT NULL COMMENT '修改人code',
  `modified_user_name` varchar(50) DEFAULT NULL COMMENT '修改人',
  `modified_date` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `version` int(11) DEFAULT '1' COMMENT '版本号（乐观锁）',
  `valid` tinyint(1) DEFAULT '1' COMMENT '数据有效性：1=有效；0=无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_e3dp_kb_source_code` (`e3dp_kb_source_code`),
  UNIQUE KEY `unique_e3dp_kb_source_file_name` (`file_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC COMMENT='知识库-文档来源';

CREATE TABLE `t_e3dp_kb_chunk` (
  `id` bigint(11) NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `e3dp_kb_chunk_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '唯一约束code',
  `source_id` bigint(11) NOT NULL COMMENT '所属文档',
  `chunk_ordinal` int(11) NOT NULL DEFAULT '0' COMMENT '块序号，同一文档内不可重复',
  `heading` varchar(300) NOT NULL DEFAULT '' COMMENT '章节路径',
  `content` text NOT NULL COMMENT '块正文',
  `vector` json NOT NULL COMMENT 'TF-IDF 稀疏向量；由应用写入',
  `embedding` json DEFAULT NULL COMMENT '正文稠密向量，已单位化，未建索引为空',
  `embedding_heading` json DEFAULT NULL COMMENT '章节标题稠密向量，已单位化，未建索引为空',
  `char_count` int(11) NOT NULL DEFAULT '0' COMMENT '正文字符数',
  `remark` varchar(300) DEFAULT NULL COMMENT '备注',
  `create_user_code` varchar(32) DEFAULT NULL COMMENT '创建人code',
  `create_user_name` varchar(50) DEFAULT NULL COMMENT '创建人',
  `create_date` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建日期',
  `modified_user_code` varchar(32) DEFAULT NULL COMMENT '修改人code',
  `modified_user_name` varchar(50) DEFAULT NULL COMMENT '修改人',
  `modified_date` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `version` int(11) DEFAULT '1' COMMENT '版本号（乐观锁）',
  `valid` tinyint(1) DEFAULT '1' COMMENT '数据有效性：1=有效；0=无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_e3dp_kb_chunk_code` (`e3dp_kb_chunk_code`),
  UNIQUE KEY `unique_e3dp_kb_chunk_ordinal` (`source_id`, `chunk_ordinal`),
  CONSTRAINT `fk_e3dp_kb_chunk_source_id` FOREIGN KEY (`source_id`) REFERENCES `t_e3dp_kb_source` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC COMMENT='知识库-切块，含稀疏向量与稠密向量';

-- ---------------------------------------------------------------------------
-- 配置与审计
-- ---------------------------------------------------------------------------

CREATE TABLE `t_e3dp_config_template` (
  `id` bigint(11) NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `e3dp_config_template_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '唯一约束code',
  `name` varchar(300) NOT NULL DEFAULT '默认活动模板' COMMENT '模板名',
  `is_default` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否默认模板：1 是，新建活动时复制它',
  `data` json NOT NULL COMMENT '全量参数，金额单位分；由应用写入',
  `remark` varchar(300) DEFAULT NULL COMMENT '备注',
  `create_user_code` varchar(32) DEFAULT NULL COMMENT '创建人code',
  `create_user_name` varchar(50) DEFAULT NULL COMMENT '创建人',
  `create_date` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建日期',
  `modified_user_code` varchar(32) DEFAULT NULL COMMENT '修改人code',
  `modified_user_name` varchar(50) DEFAULT NULL COMMENT '修改人',
  `modified_date` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `version` int(11) DEFAULT '1' COMMENT '版本号（乐观锁）',
  `valid` tinyint(1) DEFAULT '1' COMMENT '数据有效性：1=有效；0=无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_e3dp_config_template_code` (`e3dp_config_template_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC COMMENT='配置-默认活动模板';

CREATE TABLE `t_e3dp_config_audit` (
  `id` bigint(11) NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `e3dp_config_audit_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '唯一约束code',
  `scope` int(11) NOT NULL COMMENT '修改范围：1 template，2 campaign',
  `target_id` bigint(11) DEFAULT NULL COMMENT '目标对象 id，跨模板与活动，不建外键',
  `category` varchar(32) NOT NULL COMMENT '参数分类',
  `path` varchar(300) NOT NULL COMMENT '参数路径，如 fee.materials.pla.price',
  `old_value` text NOT NULL COMMENT '变更前值',
  `new_value` text NOT NULL COMMENT '变更后值',
  `remark` varchar(300) DEFAULT NULL COMMENT '备注',
  `create_user_code` varchar(32) DEFAULT NULL COMMENT '创建人code',
  `create_user_name` varchar(50) DEFAULT NULL COMMENT '创建人',
  `create_date` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建日期',
  `modified_user_code` varchar(32) DEFAULT NULL COMMENT '修改人code',
  `modified_user_name` varchar(50) DEFAULT NULL COMMENT '修改人',
  `modified_date` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `version` int(11) DEFAULT '1' COMMENT '版本号（乐观锁）',
  `valid` tinyint(1) DEFAULT '1' COMMENT '数据有效性：1=有效；0=无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_e3dp_config_audit_code` (`e3dp_config_audit_code`),
  KEY `idx_e3dp_config_audit_scope_target` (`scope`, `target_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC COMMENT='审计-配置修改记录，操作人记在创建人字段';

CREATE TABLE `t_e3dp_audit_log` (
  `id` bigint(11) NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `e3dp_audit_log_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '唯一约束code',
  `user_id` bigint(11) DEFAULT NULL COMMENT '操作人 id，匿名操作可空',
  `action` varchar(32) NOT NULL COMMENT '动作，如 login、order.create、val2.review',
  `target` varchar(300) NOT NULL DEFAULT '' COMMENT '操作对象',
  `detail` text NOT NULL COMMENT '详情',
  `ip` varchar(50) NOT NULL DEFAULT '' COMMENT '来源 IP，反代后取 X-Forwarded-For',
  `remark` varchar(300) DEFAULT NULL COMMENT '备注',
  `create_user_code` varchar(32) DEFAULT NULL COMMENT '创建人code',
  `create_user_name` varchar(50) DEFAULT NULL COMMENT '创建人',
  `create_date` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建日期',
  `modified_user_code` varchar(32) DEFAULT NULL COMMENT '修改人code',
  `modified_user_name` varchar(50) DEFAULT NULL COMMENT '修改人',
  `modified_date` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `version` int(11) DEFAULT '1' COMMENT '版本号（乐观锁）',
  `valid` tinyint(1) DEFAULT '1' COMMENT '数据有效性：1=有效；0=无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_e3dp_audit_log_code` (`e3dp_audit_log_code`),
  KEY `idx_e3dp_audit_log_user_id` (`user_id`),
  KEY `idx_e3dp_audit_log_create_date` (`create_date`),
  CONSTRAINT `fk_e3dp_audit_log_user_id` FOREIGN KEY (`user_id`) REFERENCES `t_sys_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC COMMENT='审计-操作日志，操作人姓名记在创建人字段';

CREATE TABLE `t_e3dp_app_setting` (
  `id` bigint(11) NOT NULL AUTO_INCREMENT COMMENT '主键id',
  `e3dp_app_setting_code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '唯一约束code',
  `setting_key` varchar(300) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs NOT NULL COMMENT '设置项键名，区分大小写',
  `setting_value` text NOT NULL COMMENT '设置值，按 value_type 解释；secret 只存密文或 KMS 引用',
  `category` int(11) NOT NULL DEFAULT '1' COMMENT '分类：1 service，2 slicer，3 external，4 misc',
  `label` varchar(50) NOT NULL DEFAULT '' COMMENT '显示名',
  `hint` text NOT NULL COMMENT '填写提示',
  `value_type` int(11) NOT NULL DEFAULT '1' COMMENT '值类型：1 str，2 int，3 float，4 bool，5 secret',
  `restart_required` tinyint(1) NOT NULL DEFAULT '0' COMMENT '修改后是否需要重启：1 需要，0 不需要',
  `remark` varchar(300) DEFAULT NULL COMMENT '备注',
  `create_user_code` varchar(32) DEFAULT NULL COMMENT '创建人code',
  `create_user_name` varchar(50) DEFAULT NULL COMMENT '创建人',
  `create_date` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建日期',
  `modified_user_code` varchar(32) DEFAULT NULL COMMENT '修改人code',
  `modified_user_name` varchar(50) DEFAULT NULL COMMENT '修改人',
  `modified_date` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  `version` int(11) DEFAULT '1' COMMENT '版本号（乐观锁）',
  `valid` tinyint(1) DEFAULT '1' COMMENT '数据有效性：1=有效；0=无效',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_e3dp_app_setting_code` (`e3dp_app_setting_code`),
  UNIQUE KEY `unique_e3dp_app_setting_key` (`setting_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC COMMENT='配置-软件全局设置';
