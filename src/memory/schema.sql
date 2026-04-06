-- Memory 模块数据库表结构

-- 长期记忆表（用户画像）
CREATE TABLE IF NOT EXISTS long_term_memory (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    content TEXT,
    user_profile JSONB DEFAULT '{}',
    preferences JSONB DEFAULT '{}',
    frequent_topics JSONB DEFAULT '[]',
    knowledge_gaps JSONB DEFAULT '[]',
    embedding VECTOR(768),  -- 需要 pgvector 扩展
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    access_count INTEGER DEFAULT 0,
    importance_score FLOAT DEFAULT 1.0,
    metadata JSONB DEFAULT '{}'
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_long_term_memory_user_id ON long_term_memory(user_id);
CREATE INDEX IF NOT EXISTS idx_long_term_memory_updated_at ON long_term_memory(updated_at);

-- 全局记忆表（企业知识）
CREATE TABLE IF NOT EXISTS global_memory (
    id VARCHAR(255) PRIMARY KEY,
    content TEXT NOT NULL,
    category VARCHAR(100),
    source VARCHAR(255),
    version VARCHAR(20) DEFAULT '1.0',
    approved BOOLEAN DEFAULT FALSE,
    tags JSONB DEFAULT '[]',
    embedding VECTOR(768),  -- 需要 pgvector 扩展
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    access_count INTEGER DEFAULT 0,
    importance_score FLOAT DEFAULT 1.0,
    metadata JSONB DEFAULT '{}'
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_global_memory_category ON global_memory(category);
CREATE INDEX IF NOT EXISTS idx_global_memory_approved ON global_memory(approved) WHERE approved = TRUE;

-- 向量相似度搜索索引（使用 pgvector）
-- CREATE INDEX IF NOT EXISTS idx_global_memory_embedding ON global_memory USING ivfflat (embedding vector_cosine_ops);

-- 技能执行历史表（用于RL优化）
CREATE TABLE IF NOT EXISTS skill_execution_history (
    id SERIAL PRIMARY KEY,
    skill_name VARCHAR(255) NOT NULL,
    user_id VARCHAR(255),
    session_id VARCHAR(255),
    params JSONB,
    success BOOLEAN,
    result_data JSONB,
    error_message TEXT,
    execution_time FLOAT,
    rating FLOAT,  -- 用户反馈评分 -1 到 1
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_skill_execution_skill_name ON skill_execution_history(skill_name);
CREATE INDEX IF NOT EXISTS idx_skill_execution_user_id ON skill_execution_history(user_id);
CREATE INDEX IF NOT EXISTS idx_skill_execution_created_at ON skill_execution_history(created_at);
