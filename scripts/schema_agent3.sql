-- ============================================================================
-- Agent 3 电商多维分析数据仓库 — 星型模型
-- 数据库: agent1 (MySQL)
-- 6 维度表 + 4 事实表
-- ============================================================================

USE agent1;

-- ============================================================================
-- 维度表
-- ============================================================================

-- 1. 日期维度
DROP TABLE IF EXISTS dim_date;
CREATE TABLE dim_date (
    id INT PRIMARY KEY COMMENT '日期ID (YYYYMMDD)',
    full_date DATE NOT NULL COMMENT '完整日期',
    year INT NOT NULL COMMENT '年',
    quarter INT NOT NULL COMMENT '季度 1-4',
    month INT NOT NULL COMMENT '月 1-12',
    day INT NOT NULL COMMENT '日 1-31',
    week_of_year INT NOT NULL COMMENT '年中第几周',
    day_of_week INT NOT NULL COMMENT '周几 (1=周一,7=周日)',
    is_weekend INT NOT NULL DEFAULT 0 COMMENT '是否周末 0/1',
    is_holiday INT NOT NULL DEFAULT 0 COMMENT '是否节假日 0/1',
    holiday_name VARCHAR(50) COMMENT '节假日名称',
    month_name VARCHAR(20) COMMENT '月份英文名'
) COMMENT='日期维度表';

-- 2. 商品类目维度（3级树）
DROP TABLE IF EXISTS dim_category;
CREATE TABLE dim_category (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '类目ID',
    name VARCHAR(50) NOT NULL COMMENT '类目名',
    parent_id INT COMMENT '父级类目ID（NULL=一级）',
    level INT NOT NULL COMMENT '层级: 1/2/3',
    sort_order INT DEFAULT 0 COMMENT '排序',
    FOREIGN KEY (parent_id) REFERENCES dim_category(id)
) COMMENT='商品类目维度（3级）';

-- 3. 商品维度
DROP TABLE IF EXISTS dim_product;
CREATE TABLE dim_product (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '商品ID',
    name VARCHAR(200) NOT NULL COMMENT '商品名',
    category_id INT NOT NULL COMMENT '三级类目ID',
    brand VARCHAR(100) COMMENT '品牌',
    unit_price DECIMAL(10,2) NOT NULL COMMENT '标准售价',
    cost_price DECIMAL(10,2) NOT NULL COMMENT '成本价',
    is_active INT NOT NULL DEFAULT 1 COMMENT '在售: 1/0',
    launch_date DATE COMMENT '上线日期',
    FOREIGN KEY (category_id) REFERENCES dim_category(id)
) COMMENT='商品维度表';

-- 4. 客户维度
DROP TABLE IF EXISTS dim_customer;
CREATE TABLE dim_customer (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '客户ID',
    name VARCHAR(50) NOT NULL COMMENT '姓名',
    gender VARCHAR(10) COMMENT '性别: male/female',
    age_group VARCHAR(20) COMMENT '年龄段',
    city VARCHAR(50) COMMENT '城市',
    province VARCHAR(50) COMMENT '省份',
    region VARCHAR(20) COMMENT '区域: 华北/华东/华南/华中/西南/西北/东北',
    register_channel VARCHAR(30) COMMENT '注册渠道: App/PC/H5/MiniProgram',
    member_tier VARCHAR(20) DEFAULT 'normal' COMMENT '会员等级: normal/silver/gold/platinum',
    register_date DATE COMMENT '注册日期'
) COMMENT='客户维度表';

-- 5. 渠道维度
DROP TABLE IF EXISTS dim_channel;
CREATE TABLE dim_channel (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '渠道ID',
    name VARCHAR(30) NOT NULL COMMENT '渠道名',
    type VARCHAR(20) NOT NULL COMMENT '渠道类型: online/offline',
    description VARCHAR(100) COMMENT '描述'
) COMMENT='渠道维度表';

-- 6. 支付方式维度
DROP TABLE IF EXISTS dim_payment;
CREATE TABLE dim_payment (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '支付方式ID',
    name VARCHAR(30) NOT NULL COMMENT '支付方式名称'
) COMMENT='支付方式维度表';

-- ============================================================================
-- 事实表
-- ============================================================================

-- 7. 订单事实表
DROP TABLE IF EXISTS fact_orders;
CREATE TABLE fact_orders (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '订单ID',
    order_no VARCHAR(30) NOT NULL UNIQUE COMMENT '订单号',
    customer_id INT NOT NULL COMMENT '客户ID',
    order_date_id INT NOT NULL COMMENT '下单日期ID',
    channel_id INT NOT NULL COMMENT '下单渠道ID',
    payment_id INT NOT NULL COMMENT '支付方式ID',
    total_amount DECIMAL(12,2) NOT NULL COMMENT '原价合计',
    discount_amount DECIMAL(12,2) DEFAULT 0 COMMENT '折扣金额',
    actual_amount DECIMAL(12,2) NOT NULL COMMENT '实付金额',
    order_status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending/paid/shipped/completed/cancelled/refunded',
    shipping_city VARCHAR(50) COMMENT '收货城市',
    shipping_province VARCHAR(50) COMMENT '收货省份',
    order_time DATETIME NOT NULL COMMENT '下单时间',
    pay_time DATETIME COMMENT '付款时间',
    delivery_days INT COMMENT '配送天数',
    INDEX idx_customer (customer_id),
    INDEX idx_date (order_date_id),
    INDEX idx_channel (channel_id),
    INDEX idx_status (order_status),
    INDEX idx_order_time (order_time)
) COMMENT='订单事实表';

-- 8. 订单明细事实表
DROP TABLE IF EXISTS fact_order_items;
CREATE TABLE fact_order_items (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '明细ID',
    order_id INT NOT NULL COMMENT '订单ID',
    product_id INT NOT NULL COMMENT '商品ID',
    quantity INT NOT NULL DEFAULT 1 COMMENT '数量',
    unit_price DECIMAL(10,2) NOT NULL COMMENT '成交单价',
    subtotal DECIMAL(12,2) NOT NULL COMMENT '小计',
    FOREIGN KEY (order_id) REFERENCES fact_orders(id),
    INDEX idx_product (product_id),
    INDEX idx_order (order_id)
) COMMENT='订单明细事实表';

-- 9. 流量事实表
DROP TABLE IF EXISTS fact_traffic;
CREATE TABLE fact_traffic (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '流量ID',
    date_id INT NOT NULL COMMENT '日期ID',
    channel_id INT NOT NULL COMMENT '渠道ID',
    uv INT DEFAULT 0 COMMENT '独立访客',
    pv INT DEFAULT 0 COMMENT '页面浏览',
    avg_duration_sec INT DEFAULT 0 COMMENT '平均停留秒数',
    bounce_rate DECIMAL(5,2) COMMENT '跳出率(%)',
    orders_count INT DEFAULT 0 COMMENT '当日下单数',
    order_amount DECIMAL(12,2) DEFAULT 0 COMMENT '当日下单金额',
    INDEX idx_traffic_date (date_id),
    INDEX idx_traffic_channel (channel_id),
    UNIQUE KEY uk_date_channel (date_id, channel_id)
) COMMENT='流量事实表';

-- 10. 营销投放事实表
DROP TABLE IF EXISTS fact_marketing;
CREATE TABLE fact_marketing (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '营销ID',
    date_id INT NOT NULL COMMENT '日期ID',
    channel_id INT NOT NULL COMMENT '投放渠道ID',
    campaign_name VARCHAR(100) NOT NULL COMMENT '活动名称',
    spend DECIMAL(10,2) NOT NULL COMMENT '投放花费',
    impressions INT DEFAULT 0 COMMENT '曝光量',
    clicks INT DEFAULT 0 COMMENT '点击量',
    conversions INT DEFAULT 0 COMMENT '转化数',
    revenue DECIMAL(12,2) DEFAULT 0 COMMENT '转化收入',
    INDEX idx_mkt_date (date_id),
    INDEX idx_mkt_channel (channel_id)
) COMMENT='营销投放事实表';
