"""
一键创建 Agent 3 的语义模型 + 逻辑外键
"""
import requests
import json

BASE = "http://127.0.0.1:8200"

# ═══════════════════════════════════════════════════════════════
# 1. 语义模型数据 — 10 张表、~70 个字段
# ═══════════════════════════════════════════════════════════════

semantic_items = [
    # ── dim_date 日期维度 ──
    {"tableName":"dim_date","columnName":"id","businessName":"日期ID","dataType":"int","synonyms":"时间ID,日期编码","businessDescription":"日期维度表主键，格式YYYYMMDD","columnComment":"日期ID (YYYYMMDD)"},
    {"tableName":"dim_date","columnName":"full_date","businessName":"完整日期","dataType":"date","synonyms":"日期,日期值","businessDescription":"完整的日期值","columnComment":"完整日期"},
    {"tableName":"dim_date","columnName":"year","businessName":"年份","dataType":"int","synonyms":"年","businessDescription":"所属年份","columnComment":"年"},
    {"tableName":"dim_date","columnName":"quarter","businessName":"季度","dataType":"int","synonyms":"Q,季度数","businessDescription":"所属季度1-4","columnComment":"季度 1-4"},
    {"tableName":"dim_date","columnName":"month","businessName":"月份","dataType":"int","synonyms":"月,月份数","businessDescription":"所属月份1-12","columnComment":"月 1-12"},
    {"tableName":"dim_date","columnName":"day","businessName":"日","dataType":"int","synonyms":"日期,天","businessDescription":"月份中的第几天1-31","columnComment":"日 1-31"},
    {"tableName":"dim_date","columnName":"week_of_year","businessName":"年中周数","dataType":"int","synonyms":"周数,第几周","businessDescription":"一年中的第几周","columnComment":"年中第几周"},
    {"tableName":"dim_date","columnName":"day_of_week","businessName":"星期几","dataType":"int","synonyms":"周几,星期,工作日序号","businessDescription":"周几，1=周一,7=周日","columnComment":"周几 (1=周一,7=周日)"},
    {"tableName":"dim_date","columnName":"is_weekend","businessName":"是否周末","dataType":"int","synonyms":"周末标志,周末","businessDescription":"是否周末，0=工作日,1=周末","columnComment":"是否周末 0/1"},
    {"tableName":"dim_date","columnName":"is_holiday","businessName":"是否节假日","dataType":"int","synonyms":"节假日标志,节假日","businessDescription":"是否节假日，0=否,1=是","columnComment":"是否节假日 0/1"},
    {"tableName":"dim_date","columnName":"holiday_name","businessName":"节假日名称","dataType":"varchar","synonyms":"节日名,节日","businessDescription":"节假日的具体名称，如春节、国庆","columnComment":"节假日名称"},
    {"tableName":"dim_date","columnName":"month_name","businessName":"月份英文名","dataType":"varchar","synonyms":"月份名","businessDescription":"月份的英文名称，如January","columnComment":"月份英文名"},

    # ── dim_category 类目维度 ──
    {"tableName":"dim_category","columnName":"id","businessName":"类目ID","dataType":"int","synonyms":"品类ID,分类ID,类目标识","businessDescription":"商品类目主键","columnComment":"类目ID"},
    {"tableName":"dim_category","columnName":"name","businessName":"类目名称","dataType":"varchar","synonyms":"品类名,分类名,类目","businessDescription":"商品类目名称","columnComment":"类目名"},
    {"tableName":"dim_category","columnName":"parent_id","businessName":"父级类目ID","dataType":"int","synonyms":"上级类目,父分类","businessDescription":"父级类目ID，NULL表示一级类目","columnComment":"父级类目ID（NULL=一级）"},
    {"tableName":"dim_category","columnName":"level","businessName":"类目层级","dataType":"int","synonyms":"层级,类目级别","businessDescription":"类目层级：1=一级,2=二级,3=三级","columnComment":"层级: 1/2/3"},
    {"tableName":"dim_category","columnName":"sort_order","businessName":"排序序号","dataType":"int","synonyms":"排序","businessDescription":"同级类目的显示排序","columnComment":"排序"},

    # ── dim_product 商品维度 ──
    {"tableName":"dim_product","columnName":"id","businessName":"商品ID","dataType":"int","synonyms":"产品ID,SKU_ID,货品ID","businessDescription":"商品主键","columnComment":"商品ID"},
    {"tableName":"dim_product","columnName":"name","businessName":"商品名称","dataType":"varchar","synonyms":"产品名,商品名,货品名","businessDescription":"商品全称","columnComment":"商品名"},
    {"tableName":"dim_product","columnName":"category_id","businessName":"所属类目ID","dataType":"int","synonyms":"三级类目,叶子类目","businessDescription":"商品所属的三级类目ID","columnComment":"三级类目ID"},
    {"tableName":"dim_product","columnName":"brand","businessName":"品牌","dataType":"varchar","synonyms":"品牌名,商标","businessDescription":"商品所属品牌","columnComment":"品牌"},
    {"tableName":"dim_product","columnName":"unit_price","businessName":"标准售价","dataType":"decimal","synonyms":"售价,单价,标价,原价","businessDescription":"商品的标准销售单价","columnComment":"标准售价"},
    {"tableName":"dim_product","columnName":"cost_price","businessName":"成本价","dataType":"decimal","synonyms":"成本,进价,采购价","businessDescription":"商品的成本单价","columnComment":"成本价"},
    {"tableName":"dim_product","columnName":"is_active","businessName":"是否在售","dataType":"int","synonyms":"在售状态,上架状态,是否上架","businessDescription":"商品是否在售：1=在售,0=下架","columnComment":"在售: 1/0"},
    {"tableName":"dim_product","columnName":"launch_date","businessName":"上线日期","dataType":"date","synonyms":"上架日期,上市日期,首发日期","businessDescription":"商品首次上线的日期","columnComment":"上线日期"},

    # ── dim_customer 客户维度 ──
    {"tableName":"dim_customer","columnName":"id","businessName":"客户ID","dataType":"int","synonyms":"用户ID,顾客ID,消费者ID","businessDescription":"客户主键","columnComment":"客户ID"},
    {"tableName":"dim_customer","columnName":"name","businessName":"客户姓名","dataType":"varchar","synonyms":"用户名,姓名,客户名","businessDescription":"客户的姓名","columnComment":"姓名"},
    {"tableName":"dim_customer","columnName":"gender","businessName":"性别","dataType":"varchar","synonyms":"性别标识","businessDescription":"性别：male=男,female=女","columnComment":"性别: male/female"},
    {"tableName":"dim_customer","columnName":"age_group","businessName":"年龄段","dataType":"varchar","synonyms":"年龄组,年龄区间","businessDescription":"客户所属年龄段：18-24/25-34/35-44/45-54/55+","columnComment":"年龄段"},
    {"tableName":"dim_customer","columnName":"city","businessName":"所在城市","dataType":"varchar","synonyms":"城市","businessDescription":"客户所在城市","columnComment":"城市"},
    {"tableName":"dim_customer","columnName":"province","businessName":"所在省份","dataType":"varchar","synonyms":"省份,省","businessDescription":"客户所在省份/直辖市","columnComment":"省份"},
    {"tableName":"dim_customer","columnName":"region","businessName":"所属区域","dataType":"varchar","synonyms":"大区,区域划分","businessDescription":"所属大区：华北/华东/华南/华中/西南/西北/东北","columnComment":"区域: 华北/华东/华南/华中/西南/西北/东北"},
    {"tableName":"dim_customer","columnName":"register_channel","businessName":"注册渠道","dataType":"varchar","synonyms":"注册来源,获客渠道","businessDescription":"客户注册渠道：App/PC/H5/MiniProgram","columnComment":"注册渠道: App/PC/H5/MiniProgram"},
    {"tableName":"dim_customer","columnName":"member_tier","businessName":"会员等级","dataType":"varchar","synonyms":"会员级别,会员类型","businessDescription":"会员等级：normal/silver/gold/platinum","columnComment":"会员等级: normal/silver/gold/platinum"},
    {"tableName":"dim_customer","columnName":"register_date","businessName":"注册日期","dataType":"date","synonyms":"注册时间","businessDescription":"客户的注册日期","columnComment":"注册日期"},

    # ── dim_channel 渠道维度 ──
    {"tableName":"dim_channel","columnName":"id","businessName":"渠道ID","dataType":"int","synonyms":"渠道编码","businessDescription":"渠道主键","columnComment":"渠道ID"},
    {"tableName":"dim_channel","columnName":"name","businessName":"渠道名称","dataType":"varchar","synonyms":"渠道名","businessDescription":"渠道名称，如App/PC/小程序","columnComment":"渠道名"},
    {"tableName":"dim_channel","columnName":"type","businessName":"渠道类型","dataType":"varchar","synonyms":"渠道分类","businessDescription":"渠道类型：online=线上,offline=线下","columnComment":"渠道类型: online/offline"},
    {"tableName":"dim_channel","columnName":"description","businessName":"渠道描述","dataType":"varchar","synonyms":"渠道说明","businessDescription":"渠道的详细描述","columnComment":"描述"},

    # ── dim_payment 支付方式维度 ──
    {"tableName":"dim_payment","columnName":"id","businessName":"支付方式ID","dataType":"int","synonyms":"支付方式编码","businessDescription":"支付方式主键","columnComment":"支付方式ID"},
    {"tableName":"dim_payment","columnName":"name","businessName":"支付方式名称","dataType":"varchar","synonyms":"支付方式,付款方式","businessDescription":"支付方式名称：微信/支付宝/银行卡等","columnComment":"支付方式名称"},

    # ── fact_orders 订单事实表 ──
    {"tableName":"fact_orders","columnName":"id","businessName":"订单ID","dataType":"int","synonyms":"订单编号,自增ID","businessDescription":"订单主键","columnComment":"订单ID"},
    {"tableName":"fact_orders","columnName":"order_no","businessName":"订单号","dataType":"varchar","synonyms":"订单编号,交易号","businessDescription":"订单唯一业务编号","columnComment":"订单号"},
    {"tableName":"fact_orders","columnName":"customer_id","businessName":"客户ID","dataType":"int","synonyms":"用户ID,买家ID","businessDescription":"下单客户的ID，关联dim_customer","columnComment":"客户ID"},
    {"tableName":"fact_orders","columnName":"order_date_id","businessName":"下单日期ID","dataType":"int","synonyms":"订单日期,交易日期","businessDescription":"下单日期ID，关联dim_date","columnComment":"下单日期ID"},
    {"tableName":"fact_orders","columnName":"channel_id","businessName":"下单渠道ID","dataType":"int","synonyms":"渠道ID,来源渠道","businessDescription":"下单渠道ID，关联dim_channel","columnComment":"下单渠道ID"},
    {"tableName":"fact_orders","columnName":"payment_id","businessName":"支付方式ID","dataType":"int","synonyms":"付款方式ID","businessDescription":"支付方式ID，关联dim_payment","columnComment":"支付方式ID"},
    {"tableName":"fact_orders","columnName":"total_amount","businessName":"原价合计","dataType":"decimal","synonyms":"商品总价,原价总额,标价合计","businessDescription":"订单中商品原价的总和（未折扣）","columnComment":"原价合计"},
    {"tableName":"fact_orders","columnName":"discount_amount","businessName":"折扣金额","dataType":"decimal","synonyms":"优惠金额,减免金额,折扣额","businessDescription":"订单享受的折扣总金额","columnComment":"折扣金额"},
    {"tableName":"fact_orders","columnName":"actual_amount","businessName":"实付金额","dataType":"decimal","synonyms":"成交金额,销售额,GMV,支付金额,交易额,实收金额","businessDescription":"用户实际支付的金额 = 原价-折扣","columnComment":"实付金额"},
    {"tableName":"fact_orders","columnName":"order_status","businessName":"订单状态","dataType":"varchar","synonyms":"状态,交易状态","businessDescription":"订单状态：pending=待支付,paid=已支付,shipped=已发货,completed=已完成,cancelled=已取消,refunded=已退款","columnComment":"pending/paid/shipped/completed/cancelled/refunded"},
    {"tableName":"fact_orders","columnName":"shipping_city","businessName":"收货城市","dataType":"varchar","synonyms":"配送城市,收货地","businessDescription":"收货地址所在城市","columnComment":"收货城市"},
    {"tableName":"fact_orders","columnName":"shipping_province","businessName":"收货省份","dataType":"varchar","synonyms":"配送省份,收货省","businessDescription":"收货地址所在省份","columnComment":"收货省份"},
    {"tableName":"fact_orders","columnName":"order_time","businessName":"下单时间","dataType":"datetime","synonyms":"下单时刻,创建时间","businessDescription":"用户下单的精确时间","columnComment":"下单时间"},
    {"tableName":"fact_orders","columnName":"pay_time","businessName":"付款时间","dataType":"datetime","synonyms":"支付时间,付款时刻","businessDescription":"用户完成付款的时间","columnComment":"付款时间"},
    {"tableName":"fact_orders","columnName":"delivery_days","businessName":"配送天数","dataType":"int","synonyms":"物流天数,配送时长,到货天数","businessDescription":"从发货到收货的天数","columnComment":"配送天数"},

    # ── fact_order_items 订单明细事实表 ──
    {"tableName":"fact_order_items","columnName":"id","businessName":"明细ID","dataType":"int","synonyms":"订单行ID,明细行","businessDescription":"订单明细主键","columnComment":"明细ID"},
    {"tableName":"fact_order_items","columnName":"order_id","businessName":"所属订单ID","dataType":"int","synonyms":"订单ID","businessDescription":"所属订单ID，关联fact_orders","columnComment":"订单ID"},
    {"tableName":"fact_order_items","columnName":"product_id","businessName":"商品ID","dataType":"int","synonyms":"产品ID,SKU","businessDescription":"购买的商品ID，关联dim_product","columnComment":"商品ID"},
    {"tableName":"fact_order_items","columnName":"quantity","businessName":"购买数量","dataType":"int","synonyms":"数量,件数,销量","businessDescription":"该商品的购买数量","columnComment":"数量"},
    {"tableName":"fact_order_items","columnName":"unit_price","businessName":"成交单价","dataType":"decimal","synonyms":"实际单价,成交价","businessDescription":"该商品的实际成交单价","columnComment":"成交单价"},
    {"tableName":"fact_order_items","columnName":"subtotal","businessName":"小计金额","dataType":"decimal","synonyms":"小计,行金额,子项合计","businessDescription":"该明细行的小计 = 数量 * 成交单价","columnComment":"小计"},

    # ── fact_traffic 流量事实表 ──
    {"tableName":"fact_traffic","columnName":"id","businessName":"流量ID","dataType":"int","synonyms":"流量记录ID","businessDescription":"流量记录主键","columnComment":"流量ID"},
    {"tableName":"fact_traffic","columnName":"date_id","businessName":"日期ID","dataType":"int","synonyms":"统计日期","businessDescription":"统计日期ID，关联dim_date","columnComment":"日期ID"},
    {"tableName":"fact_traffic","columnName":"channel_id","businessName":"渠道ID","dataType":"int","synonyms":"流量渠道","businessDescription":"流量渠道ID，关联dim_channel","columnComment":"渠道ID"},
    {"tableName":"fact_traffic","columnName":"uv","businessName":"独立访客数","dataType":"int","synonyms":"UV,访客数,独立访客","businessDescription":"当日独立访客数量","columnComment":"独立访客"},
    {"tableName":"fact_traffic","columnName":"pv","businessName":"页面浏览量","dataType":"int","synonyms":"PV,浏览量,页面访问量","businessDescription":"当日页面浏览总量","columnComment":"页面浏览"},
    {"tableName":"fact_traffic","columnName":"avg_duration_sec","businessName":"平均停留时长","dataType":"int","synonyms":"平均停留秒数,访问时长","businessDescription":"用户平均停留时长（秒）","columnComment":"平均停留秒数"},
    {"tableName":"fact_traffic","columnName":"bounce_rate","businessName":"跳出率","dataType":"decimal","synonyms":"跳出率%,跳出比例","businessDescription":"跳出率百分比","columnComment":"跳出率(%)"},
    {"tableName":"fact_traffic","columnName":"orders_count","businessName":"当日下单数","dataType":"int","synonyms":"下单量,转化订单数","businessDescription":"该渠道当日产生的下单数量","columnComment":"当日下单数"},
    {"tableName":"fact_traffic","columnName":"order_amount","businessName":"当日下单金额","dataType":"decimal","synonyms":"下单金额,GMV","businessDescription":"该渠道当日产生的下单总金额","columnComment":"当日下单金额"},

    # ── fact_marketing 营销投放事实表 ──
    {"tableName":"fact_marketing","columnName":"id","businessName":"营销记录ID","dataType":"int","synonyms":"投放记录ID","businessDescription":"营销投放记录主键","columnComment":"营销ID"},
    {"tableName":"fact_marketing","columnName":"date_id","businessName":"投放日期ID","dataType":"int","synonyms":"营销日期","businessDescription":"投放日期ID，关联dim_date","columnComment":"日期ID"},
    {"tableName":"fact_marketing","columnName":"channel_id","businessName":"投放渠道ID","dataType":"int","synonyms":"营销渠道","businessDescription":"投放渠道ID，关联dim_channel","columnComment":"投放渠道ID"},
    {"tableName":"fact_marketing","columnName":"campaign_name","businessName":"活动名称","dataType":"varchar","synonyms":"营销活动,推广活动,活动名","businessDescription":"营销活动的名称","columnComment":"活动名称"},
    {"tableName":"fact_marketing","columnName":"spend","businessName":"投放花费","dataType":"decimal","synonyms":"花费,投放费用,营销成本,推广费用","businessDescription":"营销投放的总花费金额","columnComment":"投放花费"},
    {"tableName":"fact_marketing","columnName":"impressions","businessName":"曝光量","dataType":"int","synonyms":"曝光数,展示量","businessDescription":"广告的曝光次数","columnComment":"曝光量"},
    {"tableName":"fact_marketing","columnName":"clicks","businessName":"点击量","dataType":"int","synonyms":"点击数","businessDescription":"广告的点击次数","columnComment":"点击量"},
    {"tableName":"fact_marketing","columnName":"conversions","businessName":"转化数","dataType":"int","synonyms":"转化量,成交数","businessDescription":"广告带来的转化（下单）数量","columnComment":"转化数"},
    {"tableName":"fact_marketing","columnName":"revenue","businessName":"转化收入","dataType":"decimal","synonyms":"转化GMV,广告收入","businessDescription":"广告转化带来的收入金额","columnComment":"转化收入"},
]

# ═══════════════════════════════════════════════════════════════
# 2. 逻辑外键 — 星型模型的 JOIN 关系
# ═══════════════════════════════════════════════════════════════

logical_relations = [
    # fact_orders → 维度表
    {"sourceTableName":"fact_orders","sourceColumnName":"customer_id","targetTableName":"dim_customer","targetColumnName":"id","relationType":"many_to_one","description":"订单→客户"},
    {"sourceTableName":"fact_orders","sourceColumnName":"order_date_id","targetTableName":"dim_date","targetColumnName":"id","relationType":"many_to_one","description":"订单→下单日期"},
    {"sourceTableName":"fact_orders","sourceColumnName":"channel_id","targetTableName":"dim_channel","targetColumnName":"id","relationType":"many_to_one","description":"订单→下单渠道"},
    {"sourceTableName":"fact_orders","sourceColumnName":"payment_id","targetTableName":"dim_payment","targetColumnName":"id","relationType":"many_to_one","description":"订单→支付方式"},
    # fact_order_items → 事实表 + 维度表
    {"sourceTableName":"fact_order_items","sourceColumnName":"order_id","targetTableName":"fact_orders","targetColumnName":"id","relationType":"many_to_one","description":"订单明细→订单"},
    {"sourceTableName":"fact_order_items","sourceColumnName":"product_id","targetTableName":"dim_product","targetColumnName":"id","relationType":"many_to_one","description":"订单明细→商品"},
    # fact_traffic → 维度表
    {"sourceTableName":"fact_traffic","sourceColumnName":"date_id","targetTableName":"dim_date","targetColumnName":"id","relationType":"many_to_one","description":"流量→日期"},
    {"sourceTableName":"fact_traffic","sourceColumnName":"channel_id","targetTableName":"dim_channel","targetColumnName":"id","relationType":"many_to_one","description":"流量→渠道"},
    # fact_marketing → 维度表
    {"sourceTableName":"fact_marketing","sourceColumnName":"date_id","targetTableName":"dim_date","targetColumnName":"id","relationType":"many_to_one","description":"营销→日期"},
    {"sourceTableName":"fact_marketing","sourceColumnName":"channel_id","targetTableName":"dim_channel","targetColumnName":"id","relationType":"many_to_one","description":"营销→渠道"},
    # dim_product → dim_category
    {"sourceTableName":"dim_product","sourceColumnName":"category_id","targetTableName":"dim_category","targetColumnName":"id","relationType":"many_to_one","description":"商品→三级类目"},
    # dim_category 自引用
    {"sourceTableName":"dim_category","sourceColumnName":"parent_id","targetTableName":"dim_category","targetColumnName":"id","relationType":"many_to_one","description":"类目→父级类目"},
]

# ═══════════════════════════════════════════════════════════════
# 3. 执行导入
# ═══════════════════════════════════════════════════════════════

print(f"[1/3] 导入语义模型 ({len(semantic_items)} 条)...")
resp = requests.post(f"{BASE}/api/semantic-model/batch-import", json={
    "agentId": 3,
    "items": semantic_items
})
data = resp.json()
print(f"  status={resp.status_code}")
if data.get("success"):
    r = data["data"]
    print(f"  total={r['total']}, success={r['successCount']}, fail={r['failCount']}")
    if r.get("errors"):
        for e in r["errors"]:
            print(f"  [ERR] {e}")
else:
    print(f"  FAILED: {data.get('message')}")

print(f"\n[2/3] 批量保存逻辑外键 ({len(logical_relations)} 条)...")
resp = requests.put(f"{BASE}/api/datasource/10/logical-relations", json=logical_relations)
data = resp.json()
print(f"  status={resp.status_code}, success={data.get('success')}, message={data.get('message')}")

print("\n[3/3] 验证导入结果...")
resp = requests.get(f"{BASE}/api/semantic-model?agentId=3")
sem = resp.json()
sm_count = len(sem.get("data", [])) if sem.get("success") else 0
resp = requests.get(f"{BASE}/api/datasource/10/logical-relations")
rel = resp.json()
rel_count = len(rel.get("data", [])) if rel.get("success") else 0
print(f"  语义模型: {sm_count} 条")
print(f"  逻辑外键: {rel_count} 条")
print("\n[DONE] 语义模型导入完成!")
