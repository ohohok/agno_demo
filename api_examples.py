"""
API Usage Examples for Agno AI Chat Service
Demonstrates different ways to interact with the chat API
"""
import requests
import json


# Base URL of the running service
BASE_URL = "http://localhost:7777"


def example_1_simple_chat():
    """Example 1: Simple chat message"""
    print("=" * 60)
    print("Example 1: Simple Chat")
    print("=" * 60)
    
    response = requests.post(
        f"{BASE_URL}/api/chat",
        json={
            "message": "你好，请介绍一下你自己"
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Success: {data['success']}")
        print(f"📝 Response: {data['message']}")
        print(f"🔑 Session ID: {data.get('session_id')}")
        print(f"🆔 Run ID: {data.get('run_id')}")
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")
    print()


def example_2_chat_with_user_id():
    """Example 2: Chat with custom user ID"""
    print("=" * 60)
    print("Example 2: Chat with User ID")
    print("=" * 60)
    
    response = requests.post(
        f"{BASE_URL}/api/chat",
        json={
            "message": "今天天气怎么样？",
            "user_id": "user_12345"
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Success: {data['success']}")
        print(f"📝 Response: {data['message']}")
    else:
        print(f"❌ Error: {response.status_code}")
    print()


def example_3_conversation_with_session():
    """Example 3: Multi-turn conversation using session_id"""
    print("=" * 60)
    print("Example 3: Multi-turn Conversation")
    print("=" * 60)
    
    # First message
    print("\n👤 User: 我叫小明")
    response1 = requests.post(
        f"{BASE_URL}/api/chat",
        json={"message": "我叫小明"}
    )
    
    if response1.status_code == 200:
        data1 = response1.json()
        session_id = data1.get('session_id')
        print(f"🤖 Agent: {data1['message']}")
        
        # Second message (continuing the conversation)
        print("\n👤 User: 你还记得我叫什么吗？")
        response2 = requests.post(
            f"{BASE_URL}/api/chat",
            json={
                "message": "你还记得我叫什么吗？",
                "session_id": session_id  # Use the same session_id
            }
        )
        
        if response2.status_code == 200:
            data2 = response2.json()
            print(f"🤖 Agent: {data2['message']}")
    print()


def example_4_health_check():
    """Example 4: Health check"""
    print("=" * 60)
    print("Example 4: Health Check")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/api/health")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Status: {data['status']}")
        print(f"🏥 Service: {data['service']}")
    else:
        print(f"❌ Error: {response.status_code}")
    print()


def example_5_curl_commands():
    """Example 5: cURL command examples"""
    print("=" * 60)
    print("Example 5: cURL Commands")
    print("=" * 60)
    print("\nSimple chat:")
    print("""curl -X POST http://localhost:7777/api/chat \\
     -H "Content-Type: application/json" \\
     -d '{"message": "你好"}'""")
    
    print("\n\nChat with user_id:")
    print("""curl -X POST http://localhost:7777/api/chat \\
     -H "Content-Type: application/json" \\
     -d '{"message": "你好", "user_id": "user123"}'""")
    
    print("\n\nHealth check:")
    print("curl http://localhost:7777/api/health")
    print()


def example_6_python_requests_session():
    """Example 6: Using requests.Session for persistent connection"""
    print("=" * 60)
    print("Example 6: Persistent Session")
    print("=" * 60)
    
    session = requests.Session()
    
    # Multiple messages in a session
    messages = [
        "你好",
        "你能帮我做什么？",
        "谢谢！"
    ]
    
    for i, msg in enumerate(messages, 1):
        print(f"\n👤 Message {i}: {msg}")
        response = session.post(
            f"{BASE_URL}/api/chat",
            json={"message": msg}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"🤖 Response: {data['message'][:100]}...")
    
    session.close()
    print()


def main():
    """Run all examples"""
    print("\n🚀 Agno AI Chat API Examples")
    print("Make sure the server is running: python main.py\n")
    
    try:
        # Check if server is running
        health_response = requests.get(f"{BASE_URL}/api/health", timeout=2)
        if health_response.status_code != 200:
            print("⚠️  Server might not be running properly")
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server!")
        print("Please start the server first: python main.py")
        return
    
    # Run examples
    example_1_simple_chat()
    example_2_chat_with_user_id()
    example_3_conversation_with_session()
    example_4_health_check()
    example_5_curl_commands()
    example_6_python_requests_session()
    
    print("\n✨ All examples completed!")


if __name__ == "__main__":
    main()
