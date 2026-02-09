# CozyEngine 数据库设计详细规范

> **文档版本**: v1.0  
> **创建日期**: 2026-02-09  
> **数据库**: PostgreSQL 14+  
> **配套PRD**: CozyEngine-PRD-完整需求文档-v1.0-2026-02-09.md  

---

## 📋 设计原则

1. **范式化**：遵循第三范式，避免数据冗余
2. **可扩展**：JSONB 字段支持灵活扩展
3. **软删除**：关键表支持软删除
4. **审计友好**：时间戳 + 审计表
5. **性能优先**：合理索引 + 分区策略

---

## 1. 核心表设计

### 1.1 users 表（用户）

```sql
CREATE TABLE users (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 基本信息
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    
    -- 权限与状态
    role VARCHAR(20) NOT NULL DEFAULT 'user',  -- user | admin
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- active | inactive | suspended
    
    -- 元数据
    user_metadata JSONB DEFAULT '{}',  -- 扩展字段（头像、偏好设置等）
    
    -- 时间戳
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP,
    
    -- 约束
    CONSTRAINT chk_role CHECK (role IN ('user', 'admin')),
    CONSTRAINT chk_status CHECK (status IN ('active', 'inactive', 'suspended')),
    CONSTRAINT chk_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$')
);

-- 索引设计
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_status ON users(status) WHERE status = 'active';  -- 部分索引
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_created_at ON users(created_at DESC);  -- 降序索引（最新用户）

-- GIN 索引（JSONB 查询）
CREATE INDEX idx_users_metadata_gin ON users USING GIN (user_metadata);

-- 触发器：自动更新 updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 注释
COMMENT ON TABLE users IS '用户账号表';
COMMENT ON COLUMN users.id IS '用户唯一标识（UUID）';
COMMENT ON COLUMN users.user_metadata IS 'JSONB 扩展字段：头像、偏好设置、UI 配置等';
```

**设计说明**：
- ✅ **UUID 主键**：分布式友好，避免 ID 冲突
- ✅ **部分索引**：`WHERE status = 'active'` 减少索引大小
- ✅ **约束检查**：`CHECK` 约束保证数据完整性
- ✅ **JSONB 扩展**：`user_metadata` 支持灵活扩展

**性能优化**：
- 活跃用户查询：`idx_users_status` 部分索引
- 按创建时间排序：`idx_users_created_at` 降序索引
- JSONB 查询：`idx_users_metadata_gin` GIN 索引

---

### 1.2 sessions 表（会话）

```sql
CREATE TABLE sessions (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联关系
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    personality_id VARCHAR(50) NOT NULL,  -- 人格 ID（关联配置文件）
    
    -- 基本信息
    title VARCHAR(200),  -- 会话标题
    message_count INTEGER NOT NULL DEFAULT 0,  -- 消息数量（冗余字段，便于查询）
    
    -- 统计信息
    total_tokens INTEGER DEFAULT 0,  -- 总消耗 tokens
    total_cost_usd DECIMAL(10, 6) DEFAULT 0,  -- 总费用（美元）
    
    -- 会话元数据
    session_metadata JSONB DEFAULT '{}',  -- 扩展字段（标签、摘要等）
    
    -- 时间戳
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_message_at TIMESTAMP,  -- 最后一条消息时间
    deleted_at TIMESTAMP,  -- 软删除
    
    -- 约束
    CONSTRAINT chk_message_count CHECK (message_count >= 0),
    CONSTRAINT chk_total_tokens CHECK (total_tokens >= 0),
    CONSTRAINT chk_total_cost CHECK (total_cost_usd >= 0)
);

-- 索引设计
CREATE INDEX idx_sessions_user_id ON sessions(user_id) WHERE deleted_at IS NULL;  -- 部分索引
CREATE INDEX idx_sessions_personality_id ON sessions(personality_id);
CREATE INDEX idx_sessions_created_at ON sessions(created_at DESC);
CREATE INDEX idx_sessions_last_message_at ON sessions(last_message_at DESC NULLS LAST);
CREATE INDEX idx_sessions_deleted_at ON sessions(deleted_at) WHERE deleted_at IS NOT NULL;  -- 软删除索引

-- 复合索引（常见查询）
CREATE INDEX idx_sessions_user_personality ON sessions(user_id, personality_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_sessions_user_last_message ON sessions(user_id, last_message_at DESC) WHERE deleted_at IS NULL;

-- GIN 索引
CREATE INDEX idx_sessions_metadata_gin ON sessions USING GIN (session_metadata);

-- 触发器
CREATE TRIGGER trigger_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 注释
COMMENT ON TABLE sessions IS '会话容器表（绑定用户与人格）';
COMMENT ON COLUMN sessions.message_count IS '消息数量（冗余字段，避免 COUNT 查询）';
COMMENT ON COLUMN sessions.deleted_at IS '软删除时间戳（NULL = 未删除）';
COMMENT ON COLUMN sessions.session_metadata IS 'JSONB 扩展：标签、摘要、置顶等';
```

**设计说明**：
- ✅ **软删除**：`deleted_at` 字段支持恢复
- ✅ **冗余字段**：`message_count` 避免 `COUNT(*)` 查询
- ✅ **复合索引**：`idx_sessions_user_last_message` 优化"最近会话"查询

**常见查询优化**：
```sql
-- 查询 1: 用户的活跃会话列表（按最后消息时间降序）
-- 使用索引: idx_sessions_user_last_message
SELECT * FROM sessions
WHERE user_id = $1 AND deleted_at IS NULL
ORDER BY last_message_at DESC NULLS LAST
LIMIT 20;

-- 查询 2: 统计用户会话数
-- 使用索引: idx_sessions_user_id
SELECT COUNT(*) FROM sessions
WHERE user_id = $1 AND deleted_at IS NULL;
```

---

### 1.3 messages 表（消息）

```sql
CREATE TABLE messages (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联关系
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- 消息内容
    role VARCHAR(20) NOT NULL,  -- system | user | assistant | tool
    content TEXT,  -- 消息内容（可为空，如 tool_calls）
    
    -- 消息元数据
    message_metadata JSONB DEFAULT '{}',  -- token_count, model, tool_calls, voice, etc.
    
    -- 时间戳
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,  -- 软删除（新增）
    
    -- 约束
    CONSTRAINT chk_role CHECK (role IN ('system', 'user', 'assistant', 'tool'))
);

-- 索引设计
CREATE INDEX idx_messages_session_id ON messages(session_id, created_at) WHERE deleted_at IS NULL;  -- 复合索引 + 部分索引
CREATE INDEX idx_messages_user_id ON messages(user_id);
CREATE INDEX idx_messages_created_at ON messages(created_at DESC);
CREATE INDEX idx_messages_role ON messages(role);

-- GIN 索引（元数据查询）
CREATE INDEX idx_messages_metadata_gin ON messages USING GIN (message_metadata);

-- 全文搜索索引（content）
CREATE INDEX idx_messages_content_fts ON messages USING GIN (to_tsvector('chinese', COALESCE(content, '')));

-- 注释
COMMENT ON TABLE messages IS '对话消息表（每条消息关联会话和用户）';
COMMENT ON COLUMN messages.content IS '消息内容（TEXT，支持长文本）';
COMMENT ON COLUMN messages.message_metadata IS 'JSONB 元数据：token_count, model, tool_calls, latency_ms, voice 等';
COMMENT ON COLUMN messages.deleted_at IS '软删除时间戳（新增）';
```

**设计说明**：
- ✅ **软删除**：新增 `deleted_at` 字段
- ✅ **全文搜索**：`idx_messages_content_fts` 支持中文全文检索
- ✅ **复合索引**：`idx_messages_session_id` 优化会话消息查询

**分区策略（未来优化）**：
```sql
-- 当 messages 表超过 1000 万行时，按月分区
CREATE TABLE messages (
    ...
) PARTITION BY RANGE (created_at);

-- 创建分区
CREATE TABLE messages_2026_02 PARTITION OF messages
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');

CREATE TABLE messages_2026_03 PARTITION OF messages
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

-- 自动创建分区（PostgreSQL 14+）
CREATE EXTENSION IF NOT EXISTS pg_partman;
```

**常见查询优化**：
```sql
-- 查询 1: 会话的消息历史（最常见）
-- 使用索引: idx_messages_session_id
SELECT * FROM messages
WHERE session_id = $1 AND deleted_at IS NULL
ORDER BY created_at ASC
LIMIT 100;

-- 查询 2: 全文搜索（用户搜索历史消息）
-- 使用索引: idx_messages_content_fts
SELECT * FROM messages
WHERE to_tsvector('chinese', content) @@ to_tsquery('chinese', $1)
  AND user_id = $2
  AND deleted_at IS NULL
ORDER BY created_at DESC
LIMIT 20;
```

---

### 1.4 audit_events 表（审计日志）

```sql
CREATE TABLE audit_events (
    -- 主键
    id UUID DEFAULT gen_random_uuid(),  -- 不设为 PRIMARY KEY，分区表不支持
    
    -- 关联关系
    request_id VARCHAR(100),  -- 请求 ID（关联多个事件）
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,  -- 允许 NULL（匿名请求）
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    personality_id VARCHAR(50),
    
    -- 事件信息
    event_type VARCHAR(50) NOT NULL,  -- TOOL_CALL | ENGINE_DEGRADED | AUTH_FAIL | ...
    event_level VARCHAR(20) NOT NULL DEFAULT 'info',  -- info | warning | error | critical
    
    -- 事件负载
    payload JSONB NOT NULL DEFAULT '{}',  -- 事件详细信息
    
    -- 完整性校验（新增）
    previous_hash VARCHAR(64),  -- 上一条审计事件的 hash
    signature VARCHAR(64),  -- HMAC 签名
    
    -- 时间戳
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- 约束
    CONSTRAINT chk_event_level CHECK (event_level IN ('info', 'warning', 'error', 'critical'))
) PARTITION BY RANGE (created_at);  -- 按月分区

-- 创建分区（过去 3 个月 + 未来 3 个月）
CREATE TABLE audit_events_2026_01 PARTITION OF audit_events
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

CREATE TABLE audit_events_2026_02 PARTITION OF audit_events
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');

CREATE TABLE audit_events_2026_03 PARTITION OF audit_events
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

CREATE TABLE audit_events_2026_04 PARTITION OF audit_events
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

CREATE TABLE audit_events_2026_05 PARTITION OF audit_events
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

-- 索引设计（在分区表上创建）
CREATE INDEX idx_audit_events_user_id ON audit_events(user_id, created_at DESC);
CREATE INDEX idx_audit_events_session_id ON audit_events(session_id, created_at DESC);
CREATE INDEX idx_audit_events_request_id ON audit_events(request_id);
CREATE INDEX idx_audit_events_event_type ON audit_events(event_type, created_at DESC);
CREATE INDEX idx_audit_events_event_level ON audit_events(event_level) WHERE event_level IN ('error', 'critical');  -- 部分索引
CREATE INDEX idx_audit_events_created_at ON audit_events(created_at DESC);

-- GIN 索引
CREATE INDEX idx_audit_events_payload_gin ON audit_events USING GIN (payload);

-- 注释
COMMENT ON TABLE audit_events IS '审计事件表（按月分区，保留 6 个月）';
COMMENT ON COLUMN audit_events.previous_hash IS '审计链：上一条事件的 SHA256 hash';
COMMENT ON COLUMN audit_events.signature IS 'HMAC 签名（防篡改）';
```

**分区维护脚本**：
```sql
-- 自动创建未来分区（每月执行）
DO $$
DECLARE
    partition_date DATE;
    partition_name TEXT;
    start_date TEXT;
    end_date TEXT;
BEGIN
    FOR i IN 1..3 LOOP
        partition_date := DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month' * i);
        partition_name := 'audit_events_' || TO_CHAR(partition_date, 'YYYY_MM');
        start_date := TO_CHAR(partition_date, 'YYYY-MM-DD');
        end_date := TO_CHAR(partition_date + INTERVAL '1 month', 'YYYY-MM-DD');
        
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF audit_events FOR VALUES FROM (%L) TO (%L)',
            partition_name, start_date, end_date
        );
    END LOOP;
END $$;

-- 自动删除旧分区（保留 6 个月）
DO $$
DECLARE
    partition_name TEXT;
BEGIN
    FOR partition_name IN
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename LIKE 'audit_events_%'
          AND tablename < 'audit_events_' || TO_CHAR(CURRENT_DATE - INTERVAL '6 months', 'YYYY_MM')
    LOOP
        EXECUTE 'DROP TABLE IF EXISTS ' || partition_name;
    END LOOP;
END $$;
```

**常见查询优化**：
```sql
-- 查询 1: 查询用户近 7 天的审计事件
-- 使用索引: idx_audit_events_user_id
-- 分区剪枝: 只扫描当月分区
SELECT * FROM audit_events
WHERE user_id = $1
  AND created_at >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY created_at DESC
LIMIT 100;

-- 查询 2: 查询错误/关键事件
-- 使用索引: idx_audit_events_event_level
SELECT * FROM audit_events
WHERE event_level IN ('error', 'critical')
  AND created_at >= CURRENT_DATE - INTERVAL '1 day'
ORDER BY created_at DESC;
```

---

## 2. 辅助表设计

### 2.1 personalities 表（人格配置）

```sql
CREATE TABLE personalities (
    -- 主键
    id VARCHAR(50) PRIMARY KEY,  -- 人格 ID（如 "assistant-v1"）
    
    -- 基本信息
    name VARCHAR(100) NOT NULL,
    description TEXT,
    
    -- 配置
    config JSONB NOT NULL DEFAULT '{}',  -- 完整的人格配置（system_prompt, model, tools, voice, memory_strategy）
    
    -- 状态
    is_active BOOLEAN NOT NULL DEFAULT true,
    version VARCHAR(20) NOT NULL DEFAULT '1.0',
    
    -- 时间戳
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- 创建者
    created_by UUID REFERENCES users(id) ON DELETE SET NULL
);

-- 索引
CREATE INDEX idx_personalities_is_active ON personalities(is_active) WHERE is_active = true;
CREATE INDEX idx_personalities_created_at ON personalities(created_at DESC);

-- GIN 索引
CREATE INDEX idx_personalities_config_gin ON personalities USING GIN (config);

-- 触发器
CREATE TRIGGER trigger_personalities_updated_at
    BEFORE UPDATE ON personalities
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 注释
COMMENT ON TABLE personalities IS '人格配置表（JSONB 存储完整配置）';
COMMENT ON COLUMN personalities.config IS 'JSONB 配置：system_prompt, model, allowed_tools, voice_strategy, memory_strategy';
```

---

### 2.2 api_keys 表（API 密钥管理）

```sql
CREATE TABLE api_keys (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联用户
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- 密钥信息
    key_hash VARCHAR(64) NOT NULL UNIQUE,  -- SHA256(api_key)
    key_prefix VARCHAR(10) NOT NULL,  -- 前缀（如 "sk-proj"）显示用
    name VARCHAR(100),  -- 密钥名称
    
    -- 权限
    scopes JSONB DEFAULT '[]',  -- 权限范围（如 ["chat:read", "chat:write"]）
    
    -- 限流
    rate_limit_per_minute INTEGER DEFAULT 60,
    
    -- 状态
    is_active BOOLEAN NOT NULL DEFAULT true,
    expires_at TIMESTAMP,  -- 过期时间
    
    -- 统计
    last_used_at TIMESTAMP,
    usage_count INTEGER DEFAULT 0,
    
    -- 时间戳
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP,  -- 撤销时间
    
    -- 约束
    CONSTRAINT chk_rate_limit CHECK (rate_limit_per_minute > 0)
);

-- 索引
CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash) WHERE is_active = true;
CREATE INDEX idx_api_keys_is_active ON api_keys(is_active);
CREATE INDEX idx_api_keys_expires_at ON api_keys(expires_at) WHERE expires_at IS NOT NULL;

-- 注释
COMMENT ON TABLE api_keys IS 'API 密钥管理表（支持多密钥、权限控制）';
COMMENT ON COLUMN api_keys.key_hash IS 'SHA256 hash（不存储明文）';
COMMENT ON COLUMN api_keys.scopes IS 'JSONB 权限范围数组';
```

---

## 3. 性能优化策略

### 3.1 连接池配置

```python
# backend/app/core/database.py

from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,              # 连接池大小
    max_overflow=10,           # 最大溢出连接数
    pool_pre_ping=True,        # 健康检查
    pool_recycle=3600,         # 1 小时回收连接
    echo=False,                # 生产环境关闭 SQL 日志
)
```

### 3.2 查询性能监控

```sql
-- 安装 pg_stat_statements 扩展
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- 查询最慢的 10 个查询
SELECT
    query,
    calls,
    total_exec_time,
    mean_exec_time,
    max_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- 查询缺失索引（需要 pg_stat_statements）
SELECT
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats
WHERE schemaname = 'public'
  AND tablename IN ('users', 'sessions', 'messages', 'audit_events')
ORDER BY correlation DESC;
```

### 3.3 VACUUM 策略

```sql
-- 自动 VACUUM 配置
ALTER TABLE messages SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_analyze_scale_factor = 0.02
);

-- 手动 VACUUM（维护窗口）
VACUUM ANALYZE messages;
VACUUM ANALYZE audit_events;
```

---

## 4. 数据迁移脚本

### 4.1 初始化脚本

```sql
-- backend/migrations/001_init_schema.sql

BEGIN;

-- 创建扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- 模糊搜索
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- 创建表（按依赖顺序）
\i 001_create_users.sql
\i 002_create_sessions.sql
\i 003_create_messages.sql
\i 004_create_audit_events.sql
\i 005_create_personalities.sql
\i 006_create_api_keys.sql

-- 创建索引
\i 010_create_indexes.sql

-- 插入初始数据
\i 020_seed_data.sql

COMMIT;
```

### 4.2 Seed 数据

```sql
-- backend/migrations/020_seed_data.sql

BEGIN;

-- 插入默认管理员
INSERT INTO users (id, username, email, password_hash, role, status)
VALUES (
    'a0b1c2d3-e4f5-6789-abcd-ef1234567890'::UUID,
    'admin',
    'admin@cozyengine.local',
    '$2b$12$...',  -- bcrypt hash of "changeme"
    'admin',
    'active'
);

-- 插入默认人格配置
INSERT INTO personalities (id, name, description, config, created_by)
VALUES (
    'assistant-v1',
    'Default Assistant',
    'Default conversational assistant',
    '{
        "system_prompt": "You are a helpful assistant.",
        "model": "gpt-4",
        "allowed_tools": ["search", "calculator"],
        "voice_strategy": {"enabled": true, "voice": "alloy"},
        "memory_strategy": {"enabled": true, "max_memories": 100}
    }'::JSONB,
    'a0b1c2d3-e4f5-6789-abcd-ef1234567890'::UUID
);

COMMIT;
```

---

## 5. 备份与恢复

### 5.1 备份策略

```bash
#!/bin/bash
# backend/scripts/backup_database.sh

BACKUP_DIR="/backups/cozyengine"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/cozyengine_$TIMESTAMP.sql.gz"

# 全量备份
pg_dump -h localhost -U cozyengine -d cozyengine | gzip > $BACKUP_FILE

# 只备份schema
pg_dump -h localhost -U cozyengine -d cozyengine --schema-only > "$BACKUP_DIR/schema_$TIMESTAMP.sql"

# 保留最近 7 天的备份
find $BACKUP_DIR -name "cozyengine_*.sql.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_FILE"
```

### 5.2 恢复

```bash
#!/bin/bash
# backend/scripts/restore_database.sh

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file>"
    exit 1
fi

# 恢复
gunzip -c $BACKUP_FILE | psql -h localhost -U cozyengine -d cozyengine

echo "Restore completed from: $BACKUP_FILE"
```

---

## 6. 监控指标

### 6.1 关键指标

```sql
-- 表大小监控
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    pg_total_relation_size(schemaname||'.'||tablename) AS size_bytes
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY size_bytes DESC;

-- 索引使用率
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan ASC;

-- 未使用的索引（idx_scan = 0）
SELECT
    schemaname,
    tablename,
    indexname
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
  AND idx_scan = 0
  AND indexrelname NOT LIKE '%_pkey';
```

---

## 📊 总结

**设计亮点**:
- ✅ **UUID 主键**: 分布式友好
- ✅ **软删除**: sessions, messages, users
- ✅ **JSONB 扩展**: 灵活性与性能兼顾
- ✅ **分区表**: audit_events 按月分区
- ✅ **部分索引**: 减少索引大小
- ✅ **全文搜索**: messages 支持中文检索
- ✅ **完整性校验**: audit_events HMAC 签名

**性能优化**:
- 📈 连接池: 20 + 10 overflow
- 📈 索引覆盖: 复合索引优化常见查询
- 📈 分区剪枝: audit_events 按时间范围查询
- 📈 自动 VACUUM: 保持表性能

**数据安全**:
- 🔒 约束检查: CHECK 约束保证数据完整性
- 🔒 外键级联: ON DELETE CASCADE/SET NULL
- 🔒 审计链: previous_hash + signature
- 🔒 备份策略: 每日全量 + 保留 7 天

---

**文档维护者**: CozyEngine Team  
**最后更新**: 2026-02-09  
**下次评审**: Phase 1 完成后
