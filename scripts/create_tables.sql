-- 创建 datasource 表
CREATE TABLE IF NOT EXISTS datasource (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL COMMENT '数据源名称',
    type VARCHAR(20) NOT NULL COMMENT '数据库类型: mysql/postgresql/sqlite',
    host VARCHAR(255) COMMENT '主机地址',
    port INT COMMENT '端口号',
    `database_name` VARCHAR(255) NOT NULL COMMENT '数据库名',
    username VARCHAR(100) COMMENT '用户名',
    password VARCHAR(255) COMMENT '密码',
    connection_url VARCHAR(500) COMMENT '完整连接字符串（SQLite使用）',
    test_status VARCHAR(20) NOT NULL DEFAULT 'untested' COMMENT '测试状态: untested/success/failed',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_datasource_type (type),
    INDEX idx_datasource_test_status (test_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='数据源表';

-- 创建 agent_datasource 表
CREATE TABLE IF NOT EXISTS agent_datasource (
    id INT AUTO_INCREMENT PRIMARY KEY,
    agent_id INT NOT NULL COMMENT 'Agent ID',
    datasource_id INT NOT NULL COMMENT 'Datasource ID',
    is_active TINYINT NOT NULL DEFAULT 0 COMMENT '是否激活: 0=否, 1=是',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    CONSTRAINT fk_agent_datasource_agent
        FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE CASCADE,
    CONSTRAINT fk_agent_datasource_datasource
        FOREIGN KEY (datasource_id) REFERENCES datasource(id) ON DELETE CASCADE,
    CONSTRAINT uk_agent_datasource UNIQUE (agent_id, datasource_id),
    INDEX idx_agent_datasource_agent (agent_id),
    INDEX idx_agent_datasource_datasource (datasource_id),
    INDEX idx_agent_datasource_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Agent-Datasource关联表';
