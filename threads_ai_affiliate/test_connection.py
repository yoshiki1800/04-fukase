import os
import sys
import requests

sys.path.insert(0, os.path.dirname(__file__))
from config.env_loader import load_env
import anthropic

load_env()

def test_claude():
    print("=== Claude API テスト ===")
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=50,
        messages=[{"role": "user", "content": "「接続テスト成功」とだけ答えてください"}]
    )
    print(f"✅ Claude API: {message.content[0].text}")

def test_threads():
    print("\n=== Threads API テスト ===")
    token = os.environ["THREADS_ACCESS_TOKEN"]
    user_id = os.environ["THREADS_USER_ID"]

    url = f"https://graph.threads.net/v1.0/{user_id}?fields=id,username,name&access_token={token}"
    res = requests.get(url)
    data = res.json()

    if "error" in data:
        print(f"❌ Threads API エラー: {data['error']['message']}")
        print(f"   詳細: {data['error']}")
    else:
        print(f"✅ Threads API: @{data.get('username', '不明')} (ID: {data.get('id')})")

if __name__ == "__main__":
    test_claude()
    test_threads()
