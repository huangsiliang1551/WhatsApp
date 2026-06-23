r"""
清空现有对话并重新注入测试对话。
Usage: .venv\Scripts\python.exe scripts\reset_and_seed.py
"""
import json
import urllib.request
import urllib.error
from sqlalchemy import create_engine, text

DB_URL = "postgresql://whatsapp_user:secure_password@localhost:5432/whatsapp_bot"
BASE = "http://localhost:8000"

ACTOR_HEADERS = {
    "X-Actor-Id": "admin",
    "X-Actor-Name": "Admin",
    "X-Actor-Role": "super_admin",
    "X-Actor-Account-Ids": "",
}


def api(method: str, path: str, body: dict | None = None) -> dict:
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in ACTOR_HEADERS.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req) as resp:
            text = resp.read().decode("utf-8")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as e:
        # 409 Conflict = resource already exists, treat as success
        if e.code == 409:
            body_text = e.read().decode("utf-8", errors="replace")
            print(f"  [SKIP] Already exists: {body_text[:80]}")
            return {}
        body_text = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"  [FAIL] {method} {path} -> {e.code} {body_text}")


def clear_conversations():
    """Direct DB delete: message_events → conversation_notes → messages → conversations"""
    print("=" * 50)
    print("[CLEAR] 清除现有对话数据...")
    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        with conn.begin():
            r = conn.execute(text("DELETE FROM message_events"))
            print(f"  message_events: {r.rowcount} rows deleted")
            r = conn.execute(text("DELETE FROM conversation_notes"))
            print(f"  conversation_notes: {r.rowcount} rows deleted")
            r = conn.execute(text("DELETE FROM messages"))
            print(f"  messages: {r.rowcount} rows deleted")
            r = conn.execute(text("DELETE FROM conversations"))
            print(f"  conversations: {r.rowcount} rows deleted")
    engine.dispose()
    print("[CLEAR] 完成！")


def seed():
    """Run seed (same logic as seed_test_conversations.py)"""
    accounts = [
        ("test-account-01", "北美客服组"),
        ("test-account-02", "欧洲客服组"),
        ("test-account-03", "亚太客服组"),
    ]

    # ── Accounts ──
    for aid, name in accounts:
        safe_name = name.encode("ascii", errors="replace").decode("ascii")
        print(f"[ACCOUNT] Registering {aid} ({safe_name}) ...")
        resp = api("POST", "/api/runtime/accounts", {
            "account_id": aid,
            "display_name": name,
            "provider_type": "mock",
        })
        print(f"  [OK] Created: {resp.get('display_name', safe_name)} (id={resp.get('account_id')})")

    print()

    # ── Enable AI for each account ──
    for aid, name in accounts:
        print(f"[AI] Enabling AI for {aid} ...")
        resp = api("POST", f"/api/runtime/accounts/{aid}/ai", {"enabled": True})
        print(f"  [OK] AI enabled: {resp.get('account_ai_enabled')}")

    # ── Register Agents ──
    agents_map = {
        "test-account-01": [("agent-cn-console", "中文客服台", "online")],
        "test-account-02": [("agent-cn-console", "中文客服台", "online")],
        "test-account-03": [("agent-cn-console", "中文客服台", "online")],
    }
    for aid, agents in agents_map.items():
        for agent_id, display, status in agents:
            print(f"[AGENT] Registering {agent_id} for {aid} ...")
            resp = api("POST", "/api/runtime/agents", {
                "account_id": aid,
                "agent_id": agent_id,
                "display_name": display,
                "status": status,
                "is_active": True,
            })
            print(f"  [OK] Agent registered: {resp.get('display_name', agent_id)}")

    print()

    # ── Register AppUsers ──
    users = [
        ("test-account-01", "customer-zh-01", "中文客户01", "zh-CN"),
        ("test-account-01", "customer-en-01", "EnglishCustomer01", "en"),
        ("test-account-01", "customer-es-01", "ClienteES01", "es"),
        ("test-account-02", "customer-zh-02", "中文客户02", "zh-CN"),
        ("test-account-02", "customer-en-02", "EnglishCustomer02", "en"),
        ("test-account-03", "customer-ja-01", "日本のお客様01", "ja"),
        ("test-account-03", "customer-en-03", "EnglishCustomer03", "en"),
        ("test-account-03", "customer-zh-03", "中文客户03", "zh-CN"),
    ]
    for aid, uid, display, lang in users:
        safe_display = display.encode("ascii", errors="replace").decode("ascii")[:20]
        print(f"[USER] Creating {uid} ({safe_display}) for {aid} ...")
        resp = api("POST", "/api/platform/users", {
            "account_id": aid,
            "public_user_id": uid,
            "display_name": display,
            "language_code": lang,
            "is_anonymous": False,
            "lifecycle_status": "active",
            "restrict_task_claim": False,
            "identities": [],
            "tag_keys": [],
        })
        uid_resp = resp.get("public_user_id", uid)
        print(f"  [OK] Created: {uid_resp}")

    print()

    # ── Mock inbound messages (creates conversations) ──
    messages = [
        # account-01 conv-001-zh: 长对话 + 表情
        ("test-account-01", "conv-001-zh", "customer-zh-01", "你好，我的订单还没收到，能帮我查一下吗？", "ai"),
        ("test-account-01", "conv-001-zh", "customer-zh-01", "订单号是 ORD-20260601-8842", "ai"),
        ("test-account-01", "conv-001-zh", "customer-zh-01", "我已经等了一周了 😞 还没有任何更新", "ai"),
        ("test-account-01", "conv-001-zh", "customer-zh-01", "请帮我加急处理一下，谢谢！这是给女朋友的生日礼物🎂🎁", "ai"),
        ("test-account-01", "conv-001-zh", "customer-zh-01", "如果今天还不能发货，我就只能申请退款了 😭", "ai"),
        ("test-account-01", "conv-001-zh", "customer-zh-01", "另外你们能否确认一下收货地址：北京市海淀区中关村大街1号 🏠", "ai"),
        # account-01 conv-002-en: 长对话 + 表情
        ("test-account-01", "conv-002-en", "customer-en-01", "Hi, I need help with a refund for my last purchase.", "ai"),
        ("test-account-01", "conv-002-en", "customer-en-01", "The item was damaged when it arrived 📦💥", "ai"),
        ("test-account-01", "conv-002-en", "customer-en-01", "I've attached photos of the damage. Can you see them?", "ai"),
        ("test-account-01", "conv-002-en", "customer-en-01", "This is really frustrating 😤 I paid $129 for this and it arrived broken", "ai"),
        ("test-account-01", "conv-002-en", "customer-en-01", "Do you offer free returns? Or do I have to pay for shipping? 💰", "ai"),
        ("test-account-01", "conv-002-en", "customer-en-01", "Also, can I get a replacement instead of a refund? I do want the product, just not broken 😅", "ai"),
        # account-01 conv-003-es: 中等长度
        ("test-account-01", "conv-003-es", "customer-es-01", "Hola, ¿pueden ayudarme con mi pedido?", "ai"),
        ("test-account-01", "conv-003-es", "customer-es-01", "El número de pedido es ES-20260515-3391 📦", "ai"),
        ("test-account-01", "conv-003-es", "customer-es-01", "¿Cuánto tiempo tarda el envío internacional? ✈️", "ai"),
        ("test-account-01", "conv-003-es", "customer-es-01", "Necesito que llegue antes del viernes, es urgente ⏰", "ai"),
        # account-02 conv-004-zh: 长对话 + 表情
        ("test-account-02", "conv-004-zh", "customer-zh-02", "我想修改我的收货地址", "echo"),
        ("test-account-02", "conv-004-zh", "customer-zh-02", "新地址是：上海市浦东新区张江路100号", "echo"),
        ("test-account-02", "conv-004-zh", "customer-zh-02", "邮编是 201203 📮", "echo"),
        ("test-account-02", "conv-004-zh", "customer-zh-02", "收件人电话也改一下：138xxxx5678 📱", "echo"),
        ("test-account-02", "conv-004-zh", "customer-zh-02", "请问改好后大概多久能发货？🚚", "echo"),
        ("test-account-02", "conv-004-zh", "customer-zh-02", "另外之前的地址请帮我删除，不要再使用了 🚫", "echo"),
        # account-02 conv-005-en: 中等长度
        ("test-account-02", "conv-005-en", "customer-en-02", "What are your business hours?", "echo"),
        ("test-account-02", "conv-005-en", "customer-en-02", "Also do you ship internationally? 🌍", "ai"),
        ("test-account-02", "conv-005-en", "customer-en-02", "I'm in Canada 🇨🇦, how much is shipping usually?", "ai"),
        ("test-account-02", "conv-005-en", "customer-en-02", "And do you offer any discounts for first-time buyers? 🎉", "ai"),
        # account-03 conv-006-ja: 中等长度 + 表情
        ("test-account-03", "conv-006-ja", "customer-ja-01", "こんにちは、配送状況を確認したいです。", "ai"),
        ("test-account-03", "conv-006-ja", "customer-ja-01", "注文番号は JP-20260601-1001 です", "ai"),
        ("test-account-03", "conv-006-ja", "customer-ja-01", "届け先の更新がありません…不安です 😰", "ai"),
        ("test-account-03", "conv-006-ja", "customer-ja-01", "来週の火曜日までに届きますか？日程を教えてください 📅", "ai"),
        # account-03 conv-007-en: 长对话 + 表情
        ("test-account-03", "conv-007-en", "customer-en-03", "Hello, I would like to cancel my subscription.", "ai"),
        ("test-account-03", "conv-007-en", "customer-en-03", "Please confirm cancellation as soon as possible.", "ai"),
        ("test-account-03", "conv-007-en", "customer-en-03", "The subscription ID is SUB-2026-00981 📝", "ai"),
        ("test-account-03", "conv-007-en", "customer-en-03", "I've been a customer for 2 years but I'm not using the service anymore 😔", "ai"),
        ("test-account-03", "conv-007-en", "customer-en-03", "Will I get a refund for the remaining days this month? 🤔", "ai"),
        ("test-account-03", "conv-007-en", "customer-en-03", "Also please delete my account data after cancellation as per GDPR 🔐", "ai"),
        # account-03 conv-008-zh: 中等长度
        ("test-account-03", "conv-008-zh", "customer-zh-03", "你们的退货政策是怎样的？", "echo"),
        ("test-account-03", "conv-008-zh", "customer-zh-03", "如果商品没有质量问题但我不喜欢，可以退吗？🤷", "echo"),
        ("test-account-03", "conv-008-zh", "customer-zh-03", "退货的运费是谁承担？要多久能退到账上？💳", "echo"),
        # ── 中文长对话测试 (scroll testing) conv-009-zh ──
        ("test-account-01", "conv-009-zh", "customer-zh-01", "客服你好，我想咨询一下关于你们最新产品的信息。我最近在网上看到了你们的新品发布，非常感兴趣。", "ai"),
        ("test-account-01", "conv-009-zh", "customer-zh-01", "我看到你们有一款智能手表，型号好像是 SW-2026，能给我详细介绍一下它的功能吗？", "ai"),
        ("test-account-01", "conv-009-zh", "customer-zh-01", "我比较关心的是电池续航能力。因为我经常出差，有时候好几天都没时间充电，如果手表能用一周以上就太好了。另外防水性能怎么样？我平时游泳和跑步都会戴手表。", "ai"),
        ("test-account-01", "conv-009-zh", "customer-zh-01", "对了，你们这款手表支持微信支付和支付宝吗？我在中国国内使用比较多，移动支付功能对我来说是必须的。还有，它能不能接打电话？是不是需要插SIM卡？", "ai"),
        ("test-account-01", "conv-009-zh", "customer-zh-01", "还有健康监测功能。我需要心率监测、血氧检测、睡眠分析这些。我妈妈有高血压，我想给她也买一块，所以健康功能很重要。对了，能不能设置紧急联系人？万一老人摔倒了能自动呼叫吗？", "ai"),
        ("test-account-01", "conv-009-zh", "customer-zh-01", "价格方面，我看到官网标价是 2999 元。你们现在有什么优惠活动吗？比如学生优惠、以旧换新或者多买折扣？我打算买两块，一块自己用一块给我妈。", "ai"),
        ("test-account-01", "conv-009-zh", "customer-zh-01", "另外，你们的售后服务怎么样？保修期多久？如果屏幕碎了能免费修吗？我之前用XX品牌的手表，屏幕摔碎了一次，维修费都快赶上买新的了 😤", "ai"),
        ("test-account-01", "conv-009-zh", "customer-zh-01", "我看到你们还有配套的手机App，这个App的体验如何？能不能同步到苹果健康？我用的是iPhone，不知道兼容性怎么样。还有，手表的数据能不能导出？我想把运动数据分享给我的私人教练。", "ai"),
        ("test-account-01", "conv-009-zh", "customer-zh-01", "颜色方面，我比较喜欢黑色或者深蓝色。你们有哪些颜色可选？表带可以自己更换吗？我有时候出席正式场合想换成皮表带，运动的时候用硅胶的。", "ai"),
        ("test-account-01", "conv-009-zh", "customer-zh-01", "发货呢？我在北京，大概多久能收到？能不能加急？另外快递用哪家？我希望用顺丰，因为之前遇到过其他快递送货上门的服务不太好。", "ai"),
        ("test-account-01", "conv-009-zh", "customer-zh-01", "我还想问问，你们有没有实体店可以体验？我想先去店里试戴一下，看看实际大小和重量。毕竟手表是要天天戴的，舒适度很重要。如果有线下店的话，麻烦告诉我地址。", "ai"),
        ("test-account-01", "conv-009-zh", "customer-zh-01", "差点忘了问，手表系统是什么？能不能安装第三方应用？我希望至少有微信、滴滴打车、高德地图这些常用App。如果能用小程序就更好了！", "ai"),
        ("test-account-01", "conv-009-zh", "customer-zh-01", "最后一个问题：你们支持分期付款吗？如果支持的话，有哪些分期方案？我倾向于12期免息的，这样每个月也就两百多，压力不大。", "ai"),
        ("test-account-01", "conv-009-zh", "customer-zh-01", "好的，我基本了解了。那我现在就下单吧！两块黑色旗舰款，送北京海淀区。对了，能帮我备注一下：其中一块帮我设置成繁体中文界面，我妈习惯了看繁体字。谢谢！🙏", "ai"),
        ("test-account-01", "conv-009-zh", "customer-zh-01", "付款成功了！订单号是 ORD-20260612-9901。请问什么时候能发货？大概多久到？我会留意物流信息的。", "ai"),
        ("test-account-01", "conv-009-zh", "customer-zh-01", "我还有个问题：如果收到货不满意，退换货的流程是怎样的？有没有七天无理由退换？退货运费谁来承担？", "ai"),
        ("test-account-01", "conv-009-zh", "customer-zh-01", "好的谢谢你的耐心解答！你们的客服态度真的很好，比XX品牌强多了 👍 我已经把你们的店铺推荐给我的朋友们了！", "ai"),
        # ── 媒体消息测试 conv-010-zh (image/video/audio) ──
        ("test-account-01", "conv-010-zh", "customer-zh-01", "你好，我发一张产品的照片给你看看", "ai"),
        ("test-account-01", "conv-010-zh", "customer-zh-01", "[图片] 这是我收到的产品外观", "ai"),
        ("test-account-01", "conv-010-zh", "customer-zh-01", "[视频] 这是我录的开箱视频", "ai"),
        ("test-account-01", "conv-010-zh", "customer-zh-01", "还有一个问题，你能听到我发的语音吗？", "ai"),
        ("test-account-01", "conv-010-zh", "customer-zh-01", "[语音] 喂你好，我想问一下这个产品的使用方法", "ai"),
        ("test-account-01", "conv-010-zh", "customer-zh-01", "我也发了一个文档，里面有详细的问题描述", "ai"),
        ("test-account-01", "conv-010-zh", "customer-zh-01", "[文件] product_issue_report.pdf", "ai"),
        ("test-account-01", "conv-010-zh", "customer-zh-01", "你能看到我发的这些文件吗？图片、视频和语音都能正常打开吗？", "ai"),
        # ── 超长单条消息测试 conv-011-zh ──
        ("test-account-02", "conv-011-zh", "customer-zh-02", "你好，我是一位长期的忠实客户，从2019年就开始使用你们的产品了。我一直对你们的产品质量和服务非常满意，也推荐给了很多朋友和家人。但是最近我发现了一些问题，想在这里详细反馈一下，希望你们能够重视并改进。\n\n首先，关于产品质量方面：最近购买的几件商品，虽然整体质量还过得去，但相比之前的批次，我感觉有一些细微的差异。比如说材质的手感不如以前细腻，包装也变得简陋了一些。我理解你们可能面临成本压力，但品质下降会影响用户对品牌的信任。\n\n其次，物流体验方面：最近两次下单，发货速度明显变慢了。以前下单后第二天就能发货，现在要等三四天。而且物流信息的更新也不够及时，有时候我查不到包裹的具体位置。这让我比较焦虑，尤其是购买重要物品的时候。\n\n第三，客服响应方面：我记得以前找客服基本上即时回复的，但现在经常需要排队等待。虽然你们的AI客服能解决一些简单问题，但遇到复杂情况时转人工的等待时间太长了。希望你们能增加人工客服的人手，或者优化AI客服的能力。\n\n第四，退换货流程：我上次退货时发现流程变得复杂了很多。以前直接在App里申请就完事了，现在要填各种表单，还要上传很多证明材料。虽然我理解这是为了防止恶意退货，但对于真实用户来说体验确实不够友好。\n\n最后我想说的是，作为一个老用户，我是真心希望你们越来越好。以上这些问题，如果能得到改善，我会继续支持你们的。如果方便的话，希望能有专门的客户经理联系我，我们可以深入沟通一下。谢谢！", "ai"),
        ("test-account-02", "conv-011-zh", "customer-zh-02", "哦对了，我还有一些具体的建议想补充。关于产品线方面，我注意到你们最近下架了好几款我常用的小配件，比如那个便携充电线，我用着特别顺手。能不能考虑重新上架或者推出替代产品？\n\n另外关于你们的会员体系，我觉得等级之间的权益差异不够明显。我现在是金卡会员，但说实话除了免运费外，没有感受到太多特别的服务。能否考虑增加一些专属优惠、生日礼品、优先体验新品的权益？\n\n还有就是App的功能方面，我发现在离线状态下很多功能都用不了。比如我看不了已购订单、也查不到物流信息。如果在没有网络的地方（比如飞机上），这些基本信息还是希望能看到的。", "ai"),
        # ── 快速连续消息测试 conv-012-zh ──
        ("test-account-02", "conv-012-zh", "customer-zh-02", "在吗", "echo"),
        ("test-account-02", "conv-012-zh", "customer-zh-02", "有个事想问", "echo"),
        ("test-account-02", "conv-012-zh", "customer-zh-02", "关于我的订单", "echo"),
        ("test-account-02", "conv-012-zh", "customer-zh-02", "订单号 ORD-123", "echo"),
        ("test-account-02", "conv-012-zh", "customer-zh-02", "什么时候发货", "echo"),
        ("test-account-02", "conv-012-zh", "customer-zh-02", "着急用", "echo"),
        ("test-account-02", "conv-012-zh", "customer-zh-02", "能加急吗", "echo"),
        ("test-account-02", "conv-012-zh", "customer-zh-02", "加钱也行", "echo"),
        ("test-account-02", "conv-012-zh", "customer-zh-02", "看到回我", "echo"),
        ("test-account-02", "conv-012-zh", "customer-zh-02", "谢谢", "echo"),
    ]

    # 媒体消息类型映射：识别 [图片]/[视频]/[语音]/[文件] 前缀
    MEDIA_TYPE_MAP = {
        "[图片]": "image",
        "[视频]": "video",
        "[语音]": "audio",
        "[文件]": "document",
    }

    for aid, cid, uid, text, mode in messages:
        safe_text = text.encode("ascii", errors="replace").decode("ascii")[:50]
        # 检测媒体类型前缀
        msg_type = "text"
        display_text = text
        for prefix, mtype in MEDIA_TYPE_MAP.items():
            if text.startswith(prefix):
                msg_type = mtype
                display_text = text[len(prefix):].strip()
                break
        print(f"[MSG] [{aid}] {cid} ({uid}) type={msg_type}: \"{safe_text}...\" mode={mode}")
        body: dict = {
            "account_id": aid,
            "conversation_id": cid,
            "user_id": uid,
            "text": display_text or text,
            "mode": mode,
        }
        if msg_type != "text":
            body["message_type"] = msg_type
        resp = api("POST", "/dev/mock/inbound-message", body)
        status = resp.get("status") or resp.get("mode") or "ok"
        print(f"  [OK] -> {status}")

    print()
    print("=" * 50)
    print("[DONE] 数据重置并重新播种完成！")
    print()
    unique_conv = len({cid for _, cid, *_ in messages})
    print(f"  Accounts: {len(accounts)}")
    print(f"  Conversations: {unique_conv}")
    print(f"  Messages: {len(messages)}")
    print()
    print("Open http://localhost:5173 -> Chat Workspace")


if __name__ == "__main__":
    clear_conversations()
    seed()
