"""
测试 Agent API

运行此脚本前，请确保：
1. 数据库已创建
2. 服务已启动（python app/main.py）
"""
import requests
import json

BASE_URL = "http://localhost:8100"


def test_health():
    """测试健康检查"""
    print("\n🔍 测试健康检查...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")
    assert response.status_code == 200


def test_create_agent():
    """测试创建 Agent"""
    print("\n🔍 测试创建 Agent...")
    data = {
        "name": "测试Agent",
        "description": "这是一个测试Agent"
    }
    response = requests.post(f"{BASE_URL}/api/agents", json=data)
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    assert response.status_code == 201
    return response.json()["id"]


def test_list_agents():
    """测试列出 Agent"""
    print("\n🔍 测试列出所有 Agent...")
    response = requests.get(f"{BASE_URL}/api/agents")
    print(f"状态码: {response.status_code}")
    data = response.json()
    print(f"总数: {data['total']}")
    print(f"Agent 列表: {json.dumps(data['items'], indent=2, ensure_ascii=False)}")
    assert response.status_code == 200


def test_get_agent(agent_id):
    """测试获取 Agent 详情"""
    print(f"\n🔍 测试获取 Agent {agent_id} 详情...")
    response = requests.get(f"{BASE_URL}/api/agents/{agent_id}")
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    assert response.status_code == 200


def test_update_agent(agent_id):
    """测试更新 Agent"""
    print(f"\n🔍 测试更新 Agent {agent_id}...")
    data = {
        "name": "更新后的Agent",
        "description": "更新后的描述"
    }
    response = requests.put(f"{BASE_URL}/api/agents/{agent_id}", json=data)
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    assert response.status_code == 200


def test_publish_agent(agent_id):
    """测试发布 Agent"""
    print(f"\n🔍 测试发布 Agent {agent_id}...")
    response = requests.post(f"{BASE_URL}/api/agents/{agent_id}/publish")
    print(f"状态码: {response.status_code}")
    data = response.json()
    print(f"响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
    assert response.status_code == 200
    assert data["status"] == "published"


def test_offline_agent(agent_id):
    """测试下线 Agent"""
    print(f"\n🔍 测试下线 Agent {agent_id}...")
    response = requests.post(f"{BASE_URL}/api/agents/{agent_id}/offline")
    print(f"状态码: {response.status_code}")
    data = response.json()
    print(f"响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
    assert response.status_code == 200
    assert data["status"] == "offline"


def test_delete_agent(agent_id):
    """测试删除 Agent"""
    print(f"\n🔍 测试删除 Agent {agent_id}...")
    response = requests.delete(f"{BASE_URL}/api/agents/{agent_id}")
    print(f"状态码: {response.status_code}")
    assert response.status_code == 204


if __name__ == "__main__":
    print("=" * 60)
    print("开始测试 Agent API")
    print("=" * 60)

    try:
        # 1. 健康检查
        test_health()

        # 2. 创建 Agent
        agent_id = test_create_agent()

        # 3. 列出所有 Agent
        test_list_agents()

        # 4. 获取 Agent 详情
        test_get_agent(agent_id)

        # 5. 更新 Agent
        test_update_agent(agent_id)

        # 6. 发布 Agent
        test_publish_agent(agent_id)

        # 7. 下线 Agent
        test_offline_agent(agent_id)

        # 8. 删除 Agent
        test_delete_agent(agent_id)

        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
    except requests.exceptions.ConnectionError:
        print("\n❌ 无法连接到服务器，请确保服务已启动：")
        print("   python app/main.py")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
