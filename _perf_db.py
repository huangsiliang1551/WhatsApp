import time, json
from app.db.session import DBSessionContext
from app.db.models import Conversation, Message, AppUser, MessageEvent
from sqlalchemy import select, func

print("=== Backend DB Query Timings ===\n")

# 1. List conversations
with DBSessionContext() as s:
    start = time.time()
    convs = s.execute(select(Conversation).limit(50)).scalars().all()
    t = (time.time() - start) * 1000
    print(f"1. SELECT conversations (50): {t:.0f}ms, {len(convs)} rows")
    
    if convs:
        c = convs[0]
        aid = c.account_id
        cid = c.external_conversation_id
        print(f"   Using: account={aid}, conv={cid}")

        # 2. List messages
        start = time.time()
        msgs = s.execute(
            select(Message)
            .where(Message.account_id == aid, Message.conversation_id == c.id)
            .order_by(Message.created_at.desc())
            .limit(30)
        ).scalars().all()
        t = (time.time() - start) * 1000
        print(f"\n2. SELECT messages (30): {t:.0f}ms, {len(msgs)} rows")

        # 3. Count messages
        start = time.time()
        count = s.execute(
            select(func.count(Message.id))
            .where(Message.account_id == aid, Message.conversation_id == c.id)
        ).scalar()
        t = (time.time() - start) * 1000
        print(f"3. COUNT messages: {t:.0f}ms, total={count}")

        # 4. List message events
        start = time.time()
        events = s.execute(
            select(MessageEvent)
            .where(MessageEvent.account_id == aid, MessageEvent.conversation_id == c.id)
            .limit(100)
        ).scalars().all()
        t = (time.time() - start) * 1000
        print(f"\n4. SELECT message_events: {t:.0f}ms, {len(events)} rows")

        # 5. List customer profiles (AppUser by public_user_id in conversations)
        start = time.time()
        cust_ids = s.execute(
            select(Conversation.customer_id).where(Conversation.account_id == aid).limit(50)
        ).scalars().all()
        users = s.execute(
            select(AppUser).where(AppUser.public_user_id.in_(list(cust_ids)))
        ).scalars().all()
        t = (time.time() - start) * 1000
        print(f"\n5. SELECT customer profiles: {t:.0f}ms, {len(users)} users")

        # 6. Simulate full list_messages_with_options (with serialization)
        start = time.time()
        for msg in msgs:
            _ = {
                "id": msg.id,
                "direction": msg.direction,
                "text": (msg.content_text or "")[:50],
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            }
        t = (time.time() - start) * 1000
        print(f"\n6. Serialize {len(msgs)} messages: {t:.0f}ms")

        # 7. AI status query
        start = time.time()
        ai_enabled = s.execute(
            select(Conversation.ai_enabled, Conversation.management_mode, Conversation.status)
            .where(Conversation.account_id == aid, Conversation.external_conversation_id == cid)
        ).first()
        t = (time.time() - start) * 1000
        print(f"\n7. SELECT ai_status: {t:.0f}ms")

print("\n=== Done ===")
