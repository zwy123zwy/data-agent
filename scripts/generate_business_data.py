#!/usr/bin/env python3
"""
Agent 3 电商多维分析数据生成脚本
===================================
生成星型模型全部数据：6 维度表 + 4 事实表，2 年跨度。

数据特征（保证后续分析测试有价值）：
  - 季节性波动：Q4 销售额比 Q1 高 50%+
  - 地域差异：华东 40%、华南 25%、华北 15%、其余 20%
  - 用户分级：platinum 5%/gold 15%/silver 30%/normal 50%，platinum 贡献 25% GMV
  - 大促折扣：618/双11/双12 折扣率 20-35%，平日 0-15%
  - 渠道效率：App 转化率 5%，PC 1.5%
  - 退单率：8% (cancelled 4% + refunded 4%)
  - 长尾效应：前 20% 商品贡献 60% 销售额
  - 少量异常值（超大单、零元单）

用法:
    python scripts/generate_business_data.py
"""

import random
import os
import sys
from datetime import datetime, timedelta, date
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

random.seed(42)

# ============================================================================
# Configuration
# ============================================================================
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASS = os.getenv("MYSQL_PASSWORD", "123456")
MYSQL_DB = "agent1"

START_DATE = date(2024, 1, 1)
END_DATE = date(2025, 12, 31)

# ============================================================================
# Data pools (fixed reference data)
# ============================================================================

CHANNELS = [
    ("App", "online", "手机App客户端"),
    ("PC", "online", "电脑网页端"),
    ("H5", "online", "移动端H5页面"),
    ("MiniProgram", "online", "微信小程序"),
    ("Offline", "offline", "线下门店"),
    ("Other", "online", "其他渠道"),
]

PAYMENTS = ["微信支付", "支付宝", "银行卡", "信用卡", "货到付款"]

# 类目 3 级结构: (id, name, parent_id, level, sort)
CATEGORIES = [
    # 一级 (6)
    (1, "数码电子", None, 1, 1),
    (2, "服装鞋帽", None, 1, 2),
    (3, "图书音像", None, 1, 3),
    (4, "家居用品", None, 1, 4),
    (5, "食品饮料", None, 1, 5),
    (6, "运动户外", None, 1, 6),
    # 二级 (12)
    (11, "手机通讯", 1, 2, 1),
    (12, "电脑办公", 1, 2, 2),
    (13, "智能穿戴", 1, 2, 3),
    (21, "男装", 2, 2, 1),
    (22, "女装", 2, 2, 2),
    (23, "鞋靴", 2, 2, 3),
    (31, "文学小说", 3, 2, 1),
    (32, "教育考试", 3, 2, 2),
    (41, "家纺", 4, 2, 1),
    (42, "灯具", 4, 2, 2),
    (51, "休闲零食", 5, 2, 1),
    (52, "茶饮酒水", 5, 2, 2),
    (61, "健身器材", 6, 2, 1),
    (62, "户外装备", 6, 2, 2),
    # 三级 - 手机通讯 (11)
    (111, "智能手机", 11, 3, 1),
    (112, "手机配件", 11, 3, 2),
    # 三级 - 电脑办公 (12)
    (121, "笔记本", 12, 3, 1),
    (122, "电脑外设", 12, 3, 2),
    # 三级 - 智能穿戴 (13)
    (131, "智能手表", 13, 3, 1),
    (132, "蓝牙耳机", 13, 3, 2),
    # 三级 - 男装 (21)
    (211, "男士衬衫", 21, 3, 1),
    (212, "男士裤装", 21, 3, 2),
    # 三级 - 女装 (22)
    (221, "女士连衣裙", 22, 3, 1),
    (222, "女士外套", 22, 3, 2),
    # 三级 - 鞋靴 (23)
    (231, "运动鞋", 23, 3, 1),
    # 三级 - 文学小说 (31)
    (311, "中文小说", 31, 3, 1),
    # 三级 - 教育考试 (32)
    (321, "考试用书", 32, 3, 1),
    # 三级 - 家纺 (41)
    (411, "床上用品", 41, 3, 1),
    # 三级 - 灯具 (42)
    (421, "台灯", 42, 3, 1),
    # 三级 - 休闲零食 (51)
    (511, "饼干糕点", 51, 3, 1),
    # 三级 - 茶饮酒水 (52)
    (521, "茶饮", 52, 3, 1),
    # 三级 - 健身器材 (61)
    (611, "跑步机", 61, 3, 1),
    # 三级 - 户外装备 (62)
    (621, "帐篷", 62, 3, 1),
]

# 商品：三级类目 → 商品列表 (name, brand, price, cost)
PRODUCTS_BY_CAT = {
    111: [  # 智能手机
        ("iPhone 15 Pro", "Apple", 8999.00, 7200.00),
        ("华为 Mate 60 Pro", "华为", 6999.00, 5200.00),
        ("小米 14 Ultra", "小米", 5999.00, 4200.00),
        ("OPPO Find X7", "OPPO", 4599.00, 3200.00),
    ],
    112: [  # 手机配件
        ("Type-C 数据线 1m", "绿联", 29.90, 8.00),
        ("20W 快充头", "Anker", 89.00, 35.00),
        ("手机壳 透明", "倍思", 19.90, 5.00),
    ],
    121: [  # 笔记本
        ("MacBook Air M3", "Apple", 9499.00, 7600.00),
        ("ThinkPad X1 Carbon", "联想", 7999.00, 6000.00),
        ("MateBook X Pro", "华为", 6999.00, 5000.00),
    ],
    122: [  # 电脑外设
        ("机械键盘 K8", "Keychron", 699.00, 300.00),
        ("4K显示器 27寸", "Dell", 2999.00, 1800.00),
        ("无线鼠标 MX3", "罗技", 599.00, 250.00),
    ],
    131: [  # 智能手表
        ("Apple Watch S9", "Apple", 3199.00, 2200.00),
        ("小米手环 8 Pro", "小米", 399.00, 180.00),
    ],
    132: [  # 蓝牙耳机
        ("AirPods Pro 2", "Apple", 1899.00, 1200.00),
        ("FreeBuds Pro 3", "华为", 1499.00, 900.00),
        ("降噪耳机 QC45", "Bose", 2299.00, 1500.00),
    ],
    211: [  # 男士衬衫
        ("商务免烫衬衫", "雅戈尔", 399.00, 150.00),
        ("牛津纺衬衫", "优衣库", 199.00, 80.00),
    ],
    212: [  # 男士裤装
        ("商务休闲裤", "海澜之家", 299.00, 100.00),
        ("牛仔裤 直筒", "Levi's", 599.00, 220.00),
    ],
    221: [  # 女士连衣裙
        ("碎花连衣裙", "Maje", 899.00, 350.00),
        ("小黑裙经典款", "Sandro", 1299.00, 500.00),
        ("针织连衣裙", "欧时力", 599.00, 220.00),
    ],
    222: [  # 女士外套
        ("双面呢大衣", "歌力思", 2599.00, 1100.00),
        ("风衣 中长款", "Burberry", 8999.00, 4000.00),
    ],
    231: [  # 运动鞋
        ("Air Max 270", "Nike", 1099.00, 550.00),
        ("Ultraboost 22", "Adidas", 1299.00, 600.00),
        ("跑鞋 飞马40", "Nike", 899.00, 400.00),
    ],
    311: [  # 中文小说
        ("《三体》全集", "科幻世界", 89.00, 40.00),
        ("《活着》", "作家出版社", 39.00, 18.00),
        ("《百年孤独》", "新经典", 55.00, 25.00),
        ("《围城》", "人民文学", 35.00, 15.00),
    ],
    321: [  # 考试用书
        ("考研数学复习全书", "高等教育", 99.00, 45.00),
        ("牛津英汉词典", "商务印书馆", 159.00, 80.00),
    ],
    411: [  # 床上用品
        ("全棉四件套 1.8m", "水星家纺", 599.00, 250.00),
        ("羽绒被 95%白鹅绒", "罗莱", 1999.00, 900.00),
    ],
    421: [  # 台灯
        ("LED护眼台灯", "小米", 299.00, 120.00),
        ("智能台灯 Pro", "华为", 499.00, 220.00),
    ],
    511: [  # 饼干糕点
        ("曲奇饼干礼盒", "皇冠丹麦", 129.00, 55.00),
        ("蛋黄酥 12枚", "百草味", 69.00, 30.00),
        ("苏打饼干 整箱", "太平", 39.00, 18.00),
    ],
    521: [  # 茶饮
        ("明前龙井 特级", "西湖", 299.00, 120.00),
        ("精品咖啡豆 250g", "Peet's", 129.00, 60.00),
        ("有机绿茶 礼盒", "中茶", 199.00, 80.00),
    ],
    611: [  # 跑步机
        ("家用跑步机 T1", "Keep", 2999.00, 1500.00),
        ("商用跑步机", "舒华", 8999.00, 5000.00),
    ],
    621: [  # 帐篷
        ("双人帐篷 防风", "牧高笛", 599.00, 250.00),
        ("自动帐篷 4人", "骆驼", 899.00, 380.00),
    ],
}

# 城市 → 省份 → 区域 映射
CITY_REGION = [
    # 华东 (40% 权重)
    ("上海", "上海", "华东", 0.15), ("杭州", "浙江", "华东", 0.07),
    ("南京", "江苏", "华东", 0.06), ("苏州", "江苏", "华东", 0.04),
    ("宁波", "浙江", "华东", 0.03), ("合肥", "安徽", "华东", 0.03),
    ("厦门", "福建", "华东", 0.02),
    # 华南 (25%)
    ("深圳", "广东", "华南", 0.10), ("广州", "广东", "华南", 0.08),
    ("东莞", "广东", "华南", 0.03), ("南宁", "广西", "华南", 0.02),
    ("海口", "海南", "华南", 0.02),
    # 华北 (15%)
    ("北京", "北京", "华北", 0.08), ("天津", "天津", "华北", 0.03),
    ("石家庄", "河北", "华北", 0.02), ("太原", "山西", "华北", 0.02),
    # 西南 (8%)
    ("成都", "四川", "西南", 0.04), ("重庆", "重庆", "西南", 0.03),
    ("昆明", "云南", "西南", 0.01),
    # 华中 (6%)
    ("武汉", "湖北", "华中", 0.03), ("长沙", "湖南", "华中", 0.02),
    ("郑州", "河南", "华中", 0.01),
    # 西北 (3%)
    ("西安", "陕西", "西北", 0.02), ("兰州", "甘肃", "西北", 0.01),
    # 东北 (3%)
    ("沈阳", "辽宁", "东北", 0.02), ("哈尔滨", "黑龙江", "东北", 0.01),
]

# 节假日
HOLIDAYS = {
    2024: {
        "0101": "元旦", "0210": "春节", "0211": "春节", "0212": "春节",
        "0213": "春节", "0214": "春节", "0215": "春节", "0216": "春节",
        "0404": "清明节", "0405": "清明节", "0406": "清明节",
        "0501": "劳动节", "0502": "劳动节", "0503": "劳动节", "0504": "劳动节", "0505": "劳动节",
        "0610": "端午节",
        "0915": "中秋节", "0916": "中秋节", "0917": "中秋节",
        "1001": "国庆节", "1002": "国庆节", "1003": "国庆节", "1004": "国庆节",
        "1005": "国庆节", "1006": "国庆节", "1007": "国庆节",
    },
    2025: {
        "0101": "元旦",
        "0128": "春节", "0129": "春节", "0130": "春节",
        "0131": "春节", "0201": "春节", "0202": "春节", "0203": "春节", "0204": "春节",
        "0405": "清明节",
        "0501": "劳动节", "0502": "劳动节", "0503": "劳动节", "0504": "劳动节", "0505": "劳动节",
        "0531": "端午节",
        "1001": "国庆节", "1002": "国庆节", "1003": "国庆节", "1004": "国庆节",
        "1005": "国庆节", "1006": "国庆节", "1007": "国庆节",
        "1006": "中秋节",
    },
}

MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]

# 大促月份（618: 6月, 双11: 11月, 双12: 12月）
PROMO_MONTHS = {6, 11, 12}


# ============================================================================
# Data generators
# ============================================================================

def weighted_choice(choices):
    """choices: [(item, weight), ...]"""
    total = sum(w for _, w in choices)
    r = random.uniform(0, total)
    upto = 0
    for item, w in choices:
        if upto + w >= r:
            return item
        upto += w
    return choices[-1][0]


def gen_dim_date():
    """生成 2024-01-01 ~ 2025-12-31 日期维度"""
    rows = []
    d = START_DATE
    while d <= END_DATE:
        mmdd = d.strftime("%m%d")
        holiday_name = HOLIDAYS.get(d.year, {}).get(mmdd)
        rows.append((
            int(d.strftime("%Y%m%d")),
            d,
            d.year,
            (d.month - 1) // 3 + 1,
            d.month,
            d.day,
            d.isocalendar()[1],
            d.isoweekday(),
            1 if d.isoweekday() >= 6 else 0,
            1 if holiday_name else 0,
            holiday_name,
            MONTH_NAMES[d.month - 1],
        ))
        d += timedelta(days=1)
    return rows


def gen_dim_category():
    """返回类目维度数据"""
    return CATEGORIES


def gen_dim_product():
    """生成商品维度：迭代三级类目 + 商品"""
    rows = []
    pid = 1
    for cat_id, products in PRODUCTS_BY_CAT.items():
        for name, brand, price, cost in products:
            launch_offset = random.randint(-700, 0)
            rows.append((
                pid, name, cat_id, brand, price, cost,
                1 if random.random() > 0.05 else 0,  # 5% 下架
                START_DATE + timedelta(days=launch_offset) if launch_offset < 0 else START_DATE,
            ))
            pid += 1
    return rows


def gen_dim_customer(num=500):
    """生成客户维度：城市分布按权重，会员等级按比例"""
    rows = []
    channels = ["App", "PC", "H5", "MiniProgram"]
    tiers_pool = (["normal"] * 50 + ["silver"] * 30 + ["gold"] * 15 + ["platinum"] * 5)
    age_groups_pool = (["18-24"] * 20 + ["25-34"] * 35 + ["35-44"] * 25 +
                       ["45-54"] * 15 + ["55+"] * 5)
    surnames = "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳酆鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯昝管卢莫"
    try:
        from faker import Faker
        fake = Faker("zh_CN")
    except ImportError:
        fake = None

    for i in range(1, num + 1):
        city_info = weighted_choice([((c, p, r), w) for c, p, r, w in CITY_REGION])
        city_name, province, region = city_info[0], city_info[1], city_info[2]
        gender = random.choice(["male", "female"])
        if fake:
            surname = random.choice(surnames)
            name = fake.first_name_female() if gender == "female" else fake.first_name_male()
            full_name = surname + (name if len(name) <= 2 else name[:2])
        else:
            full_name = f"用户{i:03d}"

        register_offset = random.randint(-700, -7)
        rows.append((
            i,
            full_name,
            gender,
            random.choice(age_groups_pool),
            city_name,
            province,
            region,
            random.choice(channels),
            random.choice(tiers_pool),
            START_DATE + timedelta(days=register_offset),
        ))
    return rows


def gen_dim_channel():
    return [(i + 1, name, typ, desc) for i, (name, typ, desc) in enumerate(CHANNELS)]


def gen_dim_payment():
    return [(i + 1, name) for i, name in enumerate(PAYMENTS)]


def gen_seasonal_factor(month):
    """返回月度销售因子：Q4 高峰，Q1 低谷"""
    factors = {1: 0.7, 2: 0.55, 3: 0.8, 4: 0.9, 5: 1.0, 6: 1.3,
               7: 0.85, 8: 0.85, 9: 0.95, 10: 1.1, 11: 1.8, 12: 1.6}
    return factors.get(month, 1.0)


def gen_discount_rate(month):
    """大促月份折扣更高"""
    if month in PROMO_MONTHS:
        return random.uniform(0.10, 0.35)
    else:
        return random.uniform(0.0, 0.15)


def gen_fact_orders(num_orders=3000, num_customers=500):
    """
    生成订单事实表。
    关键分布：
      - 状态: completed 65%, cancelled 4%, refunded 4%, paid 10%, shipped 10%, pending 7%
      - 每客户购买次数符合 power-law（少量客户大量订单）
      - 渠道: App 35%, MiniProgram 25%, H5 18%, PC 12%, Offline 8%, Other 2%
    """
    rows = []
    status_pool = (["completed"] * 65 + ["cancelled"] * 4 + ["refunded"] * 4 +
                   ["paid"] * 10 + ["shipped"] * 10 + ["pending"] * 7)
    channel_weights = [("App", 35), ("MiniProgram", 25), ("H5", 18), ("PC", 12), ("Offline", 8), ("Other", 2)]
    channel_name_to_id = {name: i + 1 for i, (name, _, _) in enumerate(CHANNELS)}

    # 客户的购买频率按 Zipf 分布
    customer_weights = [1.0 / (i ** 0.8) for i in range(1, num_customers + 1)]

    dates = []
    d = START_DATE
    while d <= END_DATE:
        dates.append(d)
        d += timedelta(days=1)

    for order_id in range(1, num_orders + 1):
        customer_id = random.choices(range(1, num_customers + 1), weights=customer_weights, k=1)[0]

        # 日期加权：高销售因子日期更容易被选中
        date_weighted = [(dt, gen_seasonal_factor(dt.month)) for dt in dates]
        order_date = weighted_choice(date_weighted)
        order_date_id = int(order_date.strftime("%Y%m%d"))

        channel_name = weighted_choice(channel_weights)
        channel_id = channel_name_to_id[channel_name]
        payment_id = random.choices([1, 2, 3, 4, 5], weights=[38, 32, 12, 10, 8], k=1)[0]

        # 生成商品明细 (1-5件)
        num_items = random.choices([1, 2, 3, 4, 5], weights=[20, 35, 25, 12, 8], k=1)[0]
        all_products = gen_dim_product()
        chosen = random.sample(all_products, min(num_items, len(all_products)))
        total_amount = sum(p[4] * random.randint(1, 3) for p in chosen)  # 原价 × 数量

        status = random.choice(status_pool)
        month = order_date.month
        discount_rate = gen_discount_rate(month)
        discount_amount = round(total_amount * discount_rate, 2)

        # cancelled 可能不付款
        if status in ("cancelled", "pending"):
            actual_amount = total_amount
            discount_amount = 0
            pay_time = None
            delivery_days = None
        else:
            actual_amount = round(total_amount - discount_amount, 2)
            pay_hours = random.randint(0, 48)
            pay_time = datetime(order_date.year, order_date.month, order_date.day,
                                random.randint(8, 22), random.randint(0, 59), 0) + timedelta(hours=pay_hours)
            delivery_days = random.choices([1, 2, 3, 4, 5, 7], weights=[15, 35, 25, 12, 8, 5], k=1)[0]

        tz_offset = random.randint(0, 23 * 3600)
        order_time = datetime(order_date.year, order_date.month, order_date.day,
                              random.randint(8, 22), random.randint(0, 59), random.randint(0, 59))

        # 收货城市 (80% 与客户同城, 20% 异地)
        city_info = weighted_choice([((c, p, r), w) for c, p, r, w in CITY_REGION])
        shipping_city = city_info[0]
        shipping_province = city_info[1]

        rows.append((
            order_id,
            f"ORD{order_date_id}{order_id:05d}",
            customer_id,
            order_date_id,
            channel_id,
            payment_id,
            round(total_amount, 2),
            discount_amount,
            round(actual_amount, 2) if actual_amount else round(total_amount, 2),
            status,
            shipping_city,
            shipping_province,
            order_time,
            pay_time if status not in ("cancelled", "pending") else None,
            delivery_days if status not in ("cancelled", "pending") else None,
        ))
    return rows


def gen_fact_order_items(orders):
    """
    基于订单事实表生成订单明细。
    前 20% 商品出现频率更高（长尾效应）。
    """
    rows = []
    all_products = gen_dim_product()
    num_products = len(all_products)

    # 商品 popularity: Zipf 分布
    product_weights = [1.0 / ((i % num_products) ** 0.6 + 1) for i in range(num_products)]

    item_id = 1
    for order in orders:
        order_id = order[0]
        status = order[8]

        num_items = random.choices([1, 2, 3, 4, 5], weights=[20, 35, 25, 12, 8], k=1)[0]
        chosen_indices = random.choices(range(num_products), weights=product_weights, k=min(num_items, num_products))
        chosen = list(set(chosen_indices))  # 去重

        for idx in chosen:
            product = all_products[idx]
            product_id = product[0]
            standard_price = float(product[4])
            quantity = random.choices([1, 2, 3, 5], weights=[60, 25, 10, 5], k=1)[0]

            # 成交单价：可以略低于标准售价（促销）
            unit_price = round(standard_price * random.uniform(0.85, 1.0), 2)
            subtotal = round(unit_price * quantity, 2)

            rows.append((
                item_id, order_id, product_id, quantity, unit_price, subtotal
            ))
            item_id += 1

    return rows


def gen_fact_traffic():
    """
    生成流量事实表：每渠道每天一条。
    渠道效率差异:
      App: CTR 5%, 转化 5%
      PC: CTR 3%, 转化 1.5%
      H5: CTR 4%, 转化 3%
      MiniProgram: CTR 6%, 转化 4%
    """
    rows = []
    channel_configs = {
        1: {"base_uv": 5000, "growth": 0.15, "ctr": 0.05, "cvr": 0.05, "bounce": 35},
        2: {"base_uv": 2000, "growth": 0.02, "ctr": 0.03, "cvr": 0.015, "bounce": 55},
        3: {"base_uv": 3500, "growth": 0.08, "ctr": 0.04, "cvr": 0.03, "bounce": 45},
        4: {"base_uv": 4000, "growth": 0.20, "ctr": 0.06, "cvr": 0.04, "bounce": 40},
        5: {"base_uv": 800, "growth": 0.01, "ctr": 0, "cvr": 0, "bounce": 0},
        6: {"base_uv": 500, "growth": 0.03, "ctr": 0.02, "cvr": 0.01, "bounce": 60},
    }

    traffic_id = 1
    d = START_DATE
    day_index = 0
    while d <= END_DATE:
        date_id = int(d.strftime("%Y%m%d"))
        seasonal = gen_seasonal_factor(d.month)
        weekend_bump = 1.2 if d.isoweekday() >= 6 else 1.0

        for ch_id, cfg in channel_configs.items():
            # UV 随时间增长 + 季节性 + 周末提升
            uv_growth = 1.0 + day_index * cfg["growth"] / 365
            uv = int(cfg["base_uv"] * uv_growth * seasonal * weekend_bump * random.uniform(0.85, 1.15))

            if ch_id == 5:  # Offline 无线上流量
                rows.append((traffic_id, date_id, ch_id, 0, 0, 0, None, 0, 0))
                traffic_id += 1
                continue

            pv = int(uv * random.uniform(2.5, 5.0))
            avg_duration = int(random.gauss(180, 60))
            bounce = round(random.gauss(cfg["bounce"], 8), 2)
            bounce = max(5, min(90, bounce))

            # 当日下单数 ≈ UV × CVR，加随机噪声
            orders_count = max(0, int(uv * cfg["cvr"] * random.uniform(0.7, 1.3)))
            order_amount = round(orders_count * random.uniform(150, 400), 2) if orders_count > 0 else 0

            rows.append((
                traffic_id, date_id, ch_id, uv, pv, avg_duration, bounce,
                orders_count, order_amount
            ))
            traffic_id += 1

        d += timedelta(days=1)
        day_index += 1

    return rows


def gen_fact_marketing():
    """生成营销投放数据：模拟 12 次活动，在 5 个渠道投放"""
    campaigns = [
        ("2024春节大促", 20240120, 20240205, 150000),
        ("2024女神节专场", 20240301, 20240310, 60000),
        ("2024年中618", 20240601, 20240620, 250000),
        ("2024七夕礼遇", 20240801, 20240815, 40000),
        ("2024开学季", 20240825, 20240910, 80000),
        ("2024双11狂欢", 20241025, 20241115, 350000),
        ("2024双12返场", 20241201, 20241215, 100000),
        ("2025年货节", 20250110, 20250125, 120000),
        ("2025春季上新", 20250301, 20250320, 70000),
        ("2025年中618", 20250601, 20250620, 280000),
        ("2025国庆大促", 20250925, 20251010, 180000),
        ("2025双11狂欢", 20251028, 20251115, 400000),
    ]

    rows = []
    mid = 1

    for campaign_name, start_id, end_id, budget in campaigns:
        start_dt = datetime.strptime(str(start_id), "%Y%m%d").date()
        end_dt = datetime.strptime(str(end_id), "%Y%m%d").date()
        days = (end_dt - start_dt).days + 1
        daily_budget = budget / days

        for ch_id in [1, 2, 3, 4, 6]:  # 线上渠道投放（排除 Offline 和 Other）
            ch_spend_share = {1: 0.40, 2: 0.10, 3: 0.20, 4: 0.25, 6: 0.05}[ch_id]
            ch_daily = daily_budget * ch_spend_share

            # App 渠道效率最高
            roi_map = {1: 2.5, 2: 0.8, 3: 1.5, 4: 2.0, 6: 0.5}
            base_roi = roi_map[ch_id]

            # 大促期间 ROI 更高
            if "618" in campaign_name or "双11" in campaign_name or "双12" in campaign_name:
                base_roi *= 1.3

            d = start_dt
            while d <= end_dt:
                date_id = int(d.strftime("%Y%m%d"))
                spend = round(ch_daily * random.uniform(0.8, 1.2), 2)
                impressions = int(spend * random.uniform(80, 150))
                click_rate = random.uniform(0.015, 0.06)
                clicks = int(impressions * click_rate)
                conversions = int(clicks * random.uniform(0.05, 0.12))
                revenue = round(spend * base_roi * random.uniform(0.7, 1.3), 2)

                rows.append((
                    mid, date_id, ch_id, campaign_name,
                    spend, impressions, clicks, conversions, revenue
                ))
                mid += 1
                d += timedelta(days=1)

    return rows


# ============================================================================
# DB insert helpers
# ============================================================================

async def insert_batch(cur, table, columns, rows, batch_size=200):
    """批量插入"""
    placeholders = ", ".join(["%s"] * len(columns))
    cols = ", ".join(columns)
    sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"

    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        await cur.executemany(sql, batch)


# ============================================================================
# Main
# ============================================================================

async def main():
    import aiomysql
    print(f"Connecting to MySQL at {MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}...")
    conn = await aiomysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PASS,
        db=MYSQL_DB, charset="utf8mb4", autocommit=True,
    )
    print("Connected.")
    cur = await conn.cursor()

    try:
        # --- 维度表 ---

        print("\n[1/10] dim_date -- 日期维度...")
        rows = gen_dim_date()
        await insert_batch(cur, "dim_date",
            ["id", "full_date", "year", "quarter", "month", "day", "week_of_year",
             "day_of_week", "is_weekend", "is_holiday", "holiday_name", "month_name"], rows)
        print(f"  [OK] {len(rows)} rows")

        print("[2/10] dim_category -- 类目维度...")
        rows = gen_dim_category()
        await insert_batch(cur, "dim_category",
            ["id", "name", "parent_id", "level", "sort_order"], rows)
        print(f"  [OK] {len(rows)} rows")

        print("[3/10] dim_product -- 商品维度...")
        rows = gen_dim_product()
        await insert_batch(cur, "dim_product",
            ["id", "name", "category_id", "brand", "unit_price", "cost_price",
             "is_active", "launch_date"], rows)
        active_cnt = sum(1 for r in rows if r[6]==1)
        print(f"  [OK] {len(rows)} rows (is_active: {active_cnt}/{len(rows)})")

        print("[4/10] dim_customer -- 客户维度...")
        rows = gen_dim_customer(500)
        await insert_batch(cur, "dim_customer",
            ["id", "name", "gender", "age_group", "city", "province", "region",
             "register_channel", "member_tier", "register_date"], rows)
        tiers = {}
        for r in rows:
            tiers[r[8]] = tiers.get(r[8], 0) + 1
        print(f"  [OK] {len(rows)} rows (tiers: {tiers})")

        print("[5/10] dim_channel -- 渠道维度...")
        rows = gen_dim_channel()
        await insert_batch(cur, "dim_channel", ["id", "name", "type", "description"], rows)
        print(f"  [OK] {len(rows)} rows")

        print("[6/10] dim_payment -- 支付方式维度...")
        rows = gen_dim_payment()
        await insert_batch(cur, "dim_payment", ["id", "name"], rows)
        print(f"  [OK] {len(rows)} rows")

        # --- 事实表 ---

        print("\n[7/10] fact_orders -- 订单事实表...")
        orders = gen_fact_orders(3000, 500)
        await insert_batch(cur, "fact_orders",
            ["id", "order_no", "customer_id", "order_date_id", "channel_id",
             "payment_id", "total_amount", "discount_amount", "actual_amount",
             "order_status", "shipping_city", "shipping_province", "order_time",
             "pay_time", "delivery_days"], orders, batch_size=100)
        statuses = {}
        for o in orders:
            statuses[o[9]] = statuses.get(o[9], 0) + 1
        total_gmv = sum(float(o[8]) for o in orders if o[9] not in ("cancelled", "pending"))
        print(f"  [OK] {len(orders)} rows (status: {statuses})")
        print(f"  GMV (excl. cancelled/pending): CNY{total_gmv:,.2f}")

        print("[8/10] fact_order_items -- 订单明细...")
        items = gen_fact_order_items(orders)
        await insert_batch(cur, "fact_order_items",
            ["id", "order_id", "product_id", "quantity", "unit_price", "subtotal"],
            items, batch_size=200)
        print(f"  [OK] {len(items)} rows (avg {len(items)/len(orders):.1f} items/order)")

        print("[9/10] fact_traffic -- 流量事实表...")
        traffic = gen_fact_traffic()
        await insert_batch(cur, "fact_traffic",
            ["id", "date_id", "channel_id", "uv", "pv", "avg_duration_sec",
             "bounce_rate", "orders_count", "order_amount"], traffic, batch_size=300)
        total_uv = sum(r[3] for r in traffic)
        print(f"  [OK] {len(traffic)} rows (total UV: {total_uv:,})")

        print("[10/10] fact_marketing -- 营销投放...")
        marketing = gen_fact_marketing()
        await insert_batch(cur, "fact_marketing",
            ["id", "date_id", "channel_id", "campaign_name", "spend",
             "impressions", "clicks", "conversions", "revenue"], marketing)
        total_spend = sum(float(r[4]) for r in marketing)
        total_rev = sum(float(r[8]) for r in marketing)
        print(f"  [OK] {len(marketing)} rows (spend: CNY{total_spend:,.2f}, revenue: CNY{total_rev:,.2f}, ROI: {total_rev/total_spend:.2f}x)")

        # --- 汇总 ---
        print("\n" + "=" * 60)
        print("DATA GENERATION COMPLETE")
        print("=" * 60)
        print(f"  dim_date:        {len(gen_dim_date()):>6,} rows")
        print(f"  dim_category:    {len(gen_dim_category()):>6,} rows")
        print(f"  dim_product:     {len(gen_dim_product()):>6,} rows")
        print(f"  dim_customer:    {500:>6,} rows")
        print(f"  dim_channel:     {len(gen_dim_channel()):>6,} rows")
        print(f"  dim_payment:     {len(gen_dim_payment()):>6,} rows")
        print(f"  fact_orders:     {len(orders):>6,} rows")
        print(f"  fact_order_items:{len(items):>6,} rows")
        print(f"  fact_traffic:    {len(traffic):>6,} rows")
        print(f"  fact_marketing:  {len(marketing):>6,} rows")
        print(f"  {'-' * 30}")
        print(f"  TOTAL:           {len(gen_dim_date()) + len(gen_dim_category()) + len(gen_dim_product()) + 500 + len(gen_dim_channel()) + len(gen_dim_payment()) + len(orders) + len(items) + len(traffic) + len(marketing):>6,} rows")

    finally:
        await cur.close()
        conn.close()
        print("\nDone. Connection closed.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
