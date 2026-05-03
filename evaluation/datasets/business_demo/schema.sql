-- ============================================================================
-- 电商业务 Demo 数据库 Schema
-- 场景: 一个在线商城，包含用户、商品、订单、类目
--
-- 表关系:
--   users 1──N orders 1──N order_items N──1 products N──1 categories
--   categories 自引用 (parent_id) 支持二级类目
-- ============================================================================

CREATE TABLE categories (
    id          INT PRIMARY KEY AUTO_INCREMENT  COMMENT '类目ID',
    name        VARCHAR(50)  NOT NULL           COMMENT '类目名称',
    parent_id   INT          DEFAULT NULL       COMMENT '父类目ID (NULL=一级类目)',
    sort_order  INT          DEFAULT 0          COMMENT '排序权重',
    created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) COMMENT '商品类目表';

CREATE TABLE products (
    id          INT PRIMARY KEY AUTO_INCREMENT  COMMENT '商品ID',
    name        VARCHAR(200) NOT NULL           COMMENT '商品名称',
    category_id INT          NOT NULL           COMMENT '所属类目ID',
    price       DECIMAL(10,2) NOT NULL          COMMENT '售价',
    cost        DECIMAL(10,2) NOT NULL          COMMENT '成本价',
    stock       INT          DEFAULT 0          COMMENT '库存数量',
    status      VARCHAR(20)  DEFAULT 'active'   COMMENT '状态: active/offline/discontinued',
    image_url   VARCHAR(500) DEFAULT NULL       COMMENT '商品图片URL',
    created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '上架时间',
    updated_at  DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (category_id) REFERENCES categories(id)
) COMMENT '商品表';

CREATE TABLE users (
    id            INT PRIMARY KEY AUTO_INCREMENT COMMENT '用户ID',
    name          VARCHAR(50)  NOT NULL          COMMENT '用户昵称',
    email         VARCHAR(100) DEFAULT NULL      COMMENT '邮箱',
    phone         VARCHAR(20)  DEFAULT NULL      COMMENT '手机号',
    city          VARCHAR(50)  DEFAULT NULL      COMMENT '所在城市',
    age           INT          DEFAULT NULL      COMMENT '年龄',
    gender        VARCHAR(10)  DEFAULT NULL      COMMENT '性别: male/female/unknown',
    vip_level     INT          DEFAULT 0         COMMENT 'VIP等级: 0=普通, 1=银卡, 2=金卡, 3=钻石',
    registered_at DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
    last_login_at DATETIME     DEFAULT NULL      COMMENT '最后登录时间'
) COMMENT '用户表';

CREATE TABLE orders (
    id              INT PRIMARY KEY AUTO_INCREMENT COMMENT '订单ID',
    user_id         INT           NOT NULL        COMMENT '用户ID',
    order_no        VARCHAR(32)   NOT NULL UNIQUE COMMENT '订单编号',
    total_amount    DECIMAL(12,2) NOT NULL        COMMENT '订单总金额',
    discount_amount DECIMAL(12,2) DEFAULT 0       COMMENT '折扣金额',
    actual_amount   DECIMAL(12,2) NOT NULL        COMMENT '实付金额 = total - discount',
    status          VARCHAR(20)   DEFAULT 'pending' COMMENT '状态: pending/paid/shipped/completed/cancelled/refunded',
    receiver_name   VARCHAR(50)   DEFAULT NULL    COMMENT '收货人',
    receiver_phone  VARCHAR(20)   DEFAULT NULL    COMMENT '收货电话',
    receiver_city   VARCHAR(50)   DEFAULT NULL    COMMENT '收货城市',
    remark          TEXT          DEFAULT NULL    COMMENT '订单备注',
    created_at      DATETIME      DEFAULT CURRENT_TIMESTAMP COMMENT '下单时间',
    paid_at         DATETIME      DEFAULT NULL    COMMENT '支付时间',
    completed_at    DATETIME      DEFAULT NULL    COMMENT '完成时间',
    FOREIGN KEY (user_id) REFERENCES users(id)
) COMMENT '订单表';

CREATE TABLE order_items (
    id          INT PRIMARY KEY AUTO_INCREMENT COMMENT '明细ID',
    order_id    INT           NOT NULL            COMMENT '订单ID',
    product_id  INT           NOT NULL            COMMENT '商品ID',
    quantity    INT           NOT NULL            COMMENT '购买数量',
    unit_price  DECIMAL(10,2) NOT NULL            COMMENT '购买时单价',
    subtotal    DECIMAL(12,2) NOT NULL            COMMENT '小计 = quantity * unit_price',
    FOREIGN KEY (order_id)   REFERENCES orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
) COMMENT '订单明细表';

-- ===== 索引 (加速评测中生成的查询) =====
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_products_status ON products(status);
CREATE INDEX idx_products_price ON products(price);
CREATE INDEX idx_orders_user ON orders(user_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_created ON orders(created_at);
CREATE INDEX idx_orders_actual ON orders(actual_amount);
CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_order_items_product ON order_items(product_id);
CREATE INDEX idx_users_city ON users(city);
CREATE INDEX idx_users_vip ON users(vip_level);
CREATE INDEX idx_users_registered ON users(registered_at);
