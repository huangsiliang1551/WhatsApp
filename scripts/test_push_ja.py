"""测试脚本：模拟日本客户向当前会话推送消息
用法：python scripts/test_push_ja.py
"""
import requests
import time
import random

BASE = "http://localhost:8000"
HEADERS = {
    "Content-Type": "application/json",
    "X-Actor-Id": "local-dev-admin",
    "X-Actor-Role": "super_admin",
}

# 日本语会话：test-account-03 / conv-006-ja / customer-ja-01
PAYLOAD = {
    "account_id": "test-account-03",
    "conversation_id": "conv-006-ja",
    "user_id": "customer-ja-01",
    "mode": "ai",  # AI 自动回复
}

MESSAGES = [
    "すみません、先日注文した商品がまだ届いていません。",
    "注文番号は ORD-2026-0042 です。",
    "配送状況を確認してもらえますか？",
    "お急ぎの荷物なので、できるだけ早く対応してほしいです。",
]

print("🚀 开始向日本语会话推送测试消息...\n")

for i, text in enumerate(MESSAGES, 1):
    payload = {**PAYLOAD, "text": text}
    try:
        r = requests.post(f"{BASE}/dev/mock/inbound-message", json=payload, headers=HEADERS)
        if r.status_code == 200:
            data = r.json()
            ai = data.get("ai", {})
            out = data.get("outbound", {})
            mode = out.get("delivery_mode", "?")
            if out.get("text"):
                print(f"  [{i}] 客户: {text[:50]}...")
                print(f"      回复: {out['text'][:60]}... ({mode})\n")
            else:
                print(f"  [{i}] 客户: {text[:50]}...")
                print(f"      AI: {ai.get('provider','?')}/{ai.get('model','?')} 模式={mode}\n")
        else:
            print(f"  [{i}] 失败: {r.status_code} {r.text[:100]}\n")
    except Exception as e:
        print(f"  [{i}] 异常: {e}\n")

    if i < len(MESSAGES):
        delay = random.uniform(3, 6)
        print(f"     ⏳ 等待 {delay:.0f}s ...\n")
        time.sleep(delay)

print("✅ 测试完成！请查看前端工作台。")
