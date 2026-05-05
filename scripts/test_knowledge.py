"""
知识库 API 测试脚本

用法:
  python scripts/test_knowledge.py                # 运行全部测试
  python scripts/test_knowledge.py --quick        # 快速模式 (跳过耗时操作)
  python scripts/test_knowledge.py --agent-id 3   # 指定 Agent ID (默认 3)

覆盖 8 个 API 端点:
  1. POST /api/agent-knowledge/create          创建知识
  2. GET  /api/agent-knowledge/{id}            获取详情
  3. POST /api/agent-knowledge/query/page      分页列表
  4. POST /api/agent-knowledge/search          向量检索
  5. PUT  /api/agent-knowledge/{id}            更新知识
  6. PUT  /api/agent-knowledge/recall/{id}     切换召回状态
  7. POST /api/agent-knowledge/retry-embedding/{id}  重试向量化
  8. DELETE /api/agent-knowledge/{id}          删除知识
"""
import sys
import httpx
import asyncio
import argparse

BASE_URL = "http://127.0.0.1:8100"
TIMEOUT = 120  # bge-m3 首次 embedding 较慢

PASS = 0
FAIL = 0
created_ids = []  # 记录创建的 ID，最后清理


def ok(label):
    global PASS
    PASS += 1
    print(f"  [PASS] {label}")


def err(label, detail=""):
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {label} {detail}")


async def create_document(client: httpx.AsyncClient, agent_id: int):
    """1. 创建 DOCUMENT 类型知识"""
    print("\n=== 1. 创建知识 (DOCUMENT) ===")
    r = await client.post(f"{BASE_URL}/api/agent-knowledge/create", data={
        "agentId": str(agent_id),
        "title": "测试文档—数据库表结构说明",
        "type": "DOCUMENT",
        "content": "本系统包含以下核心表：agent(智能体)、datasource(数据源)、agent_knowledge(知识库)、"
                   "semantic_model(语义模型)、query_plan(查询计划)。每张表都有createTime和updateTime字段记录时间戳。",
    }, timeout=TIMEOUT)
    j = r.json()
    if j.get("success"):
        kid = j["data"]["id"]
        created_ids.append(kid)
        ok(f"创建成功 id={kid} embeddingId={j['data'].get('embeddingId')}")
        return kid
    else:
        err("创建失败", j.get("message", ""))
        return None


async def create_qa(client: httpx.AsyncClient, agent_id: int):
    """1b. 创建 QA 类型知识"""
    print("\n=== 2. 创建知识 (QA) ===")
    r = await client.post(f"{BASE_URL}/api/agent-knowledge/create", data={
        "agentId": str(agent_id),
        "title": "如何查询Agent列表",
        "type": "QA",
        "question": "有哪些Agent可以用",
        "content": "查询所有Agent可以使用 SELECT * FROM agent WHERE status = 1。"
                   "Agent表包含name(名称)、description(描述)、category(分类)、status(状态)等字段。",
    }, timeout=TIMEOUT)
    j = r.json()
    if j.get("success"):
        kid = j["data"]["id"]
        created_ids.append(kid)
        ok(f"创建成功 id={kid} question={j['data'].get('question')}")
        return kid
    else:
        err("创建失败", j.get("message", ""))
        return None


async def get_detail(client: httpx.AsyncClient, kid: int):
    """3. 获取知识详情"""
    print(f"\n=== 3. 获取详情 id={kid} ===")
    r = await client.get(f"{BASE_URL}/api/agent-knowledge/{kid}")
    j = r.json()
    if j.get("success") and j["data"]["id"] == kid:
        d = j["data"]
        ok(f"title={d['title'][:30]} type={d['type']} enabled={d['enabled']} isRecall={d['isRecall']}")
    else:
        err("获取失败", j.get("message", ""))


async def query_page(client: httpx.AsyncClient, agent_id: int):
    """4. 分页查询"""
    print(f"\n=== 4. 分页查询 ===")
    r = await client.post(f"{BASE_URL}/api/agent-knowledge/query/page", json={
        "agentId": agent_id,
        "pageNum": 1,
        "pageSize": 10,
    })
    j = r.json()
    if j.get("success"):
        total = j.get("total", 0)
        items = j.get("data", [])
        ok(f"total={total} pageSize={j['pageSize']} pageNum={j['pageNum']}")
        for item in items[:3]:
            print(f"       id={item['id']} title={item['title'][:30]} type={item['type']}")
    else:
        err("分页查询失败", j.get("message", ""))


async def search(client: httpx.AsyncClient, agent_id: int):
    """5. 向量检索"""
    print(f"\n=== 5. 向量检索 ===")
    queries = [
        "数据库表结构",
        "Agent 怎么查询",
    ]
    for q in queries:
        r = await client.post(
            f"{BASE_URL}/api/agent-knowledge/search?agentId={agent_id}",
            json={"query": q, "topK": 3, "enabledOnly": False},
        )
        j = r.json()
        if j.get("success"):
            results = j.get("data", [])
            if results:
                top = results[0]
                ok(f"'{q}' -> #{results[0]['id']} '{results[0]['title'][:30]}' dist={results[0]['distance']:.4f}")
            else:
                err(f"'{q}' -> 无结果")
        else:
            err(f"检索失败", j.get("message", ""))


async def update_knowledge(client: httpx.AsyncClient, kid: int):
    """6. 更新知识"""
    print(f"\n=== 6. 更新知识 id={kid} ===")
    r = await client.put(f"{BASE_URL}/api/agent-knowledge/{kid}", json={
        "title": "测试文档—数据库表结构说明(已更新)",
        "content": "更新后的内容：系统包含 agent、datasource、agent_knowledge 等核心表。",
    })
    j = r.json()
    if j.get("success"):
        ok(f"标题已更新 -> {j['data']['title'][:30]}")
    else:
        err("更新失败", j.get("message", ""))


async def toggle_recall(client: httpx.AsyncClient, kid: int):
    """7. 切换召回状态"""
    print(f"\n=== 7. 切换召回状态 id={kid} ===")
    # 关闭召回
    r = await client.put(f"{BASE_URL}/api/agent-knowledge/recall/{kid}?isRecall=0")
    j = r.json()
    if j.get("success") and j["data"]["isRecall"] == 0:
        ok("isRecall 已关闭 (0)")
    else:
        err("关闭失败")
        return
    # 重新打开
    r = await client.put(f"{BASE_URL}/api/agent-knowledge/recall/{kid}?isRecall=1")
    j = r.json()
    if j.get("success") and j["data"]["isRecall"] == 1:
        ok("isRecall 已开启 (1)")
    else:
        err("开启失败")


async def retry_embedding(client: httpx.AsyncClient, kid: int):
    """8. 重试向量化"""
    print(f"\n=== 8. 重试向量化 id={kid} ===")
    r = await client.post(f"{BASE_URL}/api/agent-knowledge/retry-embedding/{kid}", timeout=TIMEOUT)
    j = r.json()
    if j.get("success"):
        status = j["data"].get("embeddingStatus", "?")
        ok(f"embeddingStatus={status}")
    else:
        err("重试失败", j.get("message", ""))


async def delete_knowledge(client: httpx.AsyncClient, kid: int):
    """9. 删除知识"""
    print(f"\n=== 9. 删除知识 id={kid} ===")
    r = await client.delete(f"{BASE_URL}/api/agent-knowledge/{kid}")
    j = r.json()
    if j.get("success"):
        created_ids.remove(kid)
        ok("删除成功")
    else:
        err("删除失败", j.get("message", ""))


async def test_with_file(client: httpx.AsyncClient, agent_id: int):
    """10. 文件上传创建知识"""
    print(f"\n=== 10. 文件上传创建知识 ===")
    import io
    file_content = "这是一个测试文件内容。\n用于验证知识库的文件上传功能。"
    files = {"file": ("test_knowledge.txt", io.BytesIO(file_content.encode()), "text/plain")}
    data = {
        "agentId": str(agent_id),
        "title": "文件上传测试",
        "type": "DOCUMENT",
    }
    r = await client.post(f"{BASE_URL}/api/agent-knowledge/create", data=data, files=files, timeout=TIMEOUT)
    j = r.json()
    if j.get("success"):
        kid = j["data"]["id"]
        created_ids.append(kid)
        ok(f"上传成功 id={kid} sourceFilename={j['data'].get('sourceFilename')}")
    else:
        err("文件上传失败", j.get("message", ""))


async def cleanup(client: httpx.AsyncClient):
    """清理所有测试数据"""
    print(f"\n=== 清理测试数据 ===")
    for kid in list(created_ids):
        r = await client.delete(f"{BASE_URL}/api/agent-knowledge/{kid}")
        if r.json().get("success"):
            created_ids.remove(kid)
            print(f"  已删除 id={kid}")
        else:
            print(f"  删除失败 id={kid}")


async def main():
    global PASS, FAIL, created_ids
    parser = argparse.ArgumentParser(description="知识库 API 测试")
    parser.add_argument("--agent-id", type=int, default=3, help="Agent ID (默认 3)")
    parser.add_argument("--quick", action="store_true", help="快速模式 (跳过向量化和文件上传)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8100", help="服务器地址")
    args = parser.parse_args()

    BASE_URL = args.base_url
    agent_id = args.agent_id

    print(f"知识库 API 测试 — Agent {agent_id}")
    print(f"服务器: {BASE_URL}")
    print(f"模式: {'快速' if args.quick else '完整'}")

    async with httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT)) as client:
        # 1-2: 创建
        doc_id = await create_document(client, agent_id)
        qa_id = await create_qa(client, agent_id)

        if doc_id:
            # 3: 详情
            await get_detail(client, doc_id)

        # 4: 分页
        await query_page(client, agent_id)

        # 5: 向量检索 (需要 embedding 完成)
        if not args.quick:
            await search(client, agent_id)

        if doc_id:
            # 6: 更新
            await update_knowledge(client, doc_id)
            # 7: 召回开关
            await toggle_recall(client, doc_id)

        # 8: 重试向量化
        if not args.quick and doc_id:
            await retry_embedding(client, doc_id)

        # 9: 文件上传
        if not args.quick:
            await test_with_file(client, agent_id)

        # 10: 分页确认最终状态
        await query_page(client, agent_id)

        # 清理
        await cleanup(client)

    print(f"\n{'='*40}")
    print(f"结果: {PASS} 通过, {FAIL} 失败")
    if FAIL > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
