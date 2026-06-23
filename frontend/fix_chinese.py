"""修复 admin-chat 文件中损坏的中文文本"""
import os

CHAT_DIR = r"e:\codex\WhatsApp\frontend\src\pages\admin-chat"

# 已知的正确文本映射 (corrupted → correct)
FIXES = {
    # ConversationList.tsx
    "placeholder=\"��������...\"": "placeholder=\"搜索会话...\"",
    "\">������...</div>": "\">加载中...</div>",
    "\">��������</div>": "\">暂无会话</div>",

    # MessagePanel.tsx - empty state
    "ѡ��һ��������ʼ����": "选择一个会话开始聊天",
    "Ctrl+1~9 ���� �� Ctrl+W ����": "Ctrl+1~9 切换 · Ctrl+W 关闭",
    "Enter ���� �� Shift+Enter ����": "Enter 发送 · Shift+Enter 换行",

    # MessagePanel.tsx - message area
    "\">�� {newMsgCount} ������Ϣ</div>": "\">↑ {newMsgCount} 条新消息</div>",

    # MessagePanel.tsx - mode label
    "conversationMode === \"ai_managed\"\n              ? \"AI ����\"\n              : conversationMode === \"human_managed\"\n                ? \"��������\"\n                : \"��������ͣ\"": "conversationMode === \"ai_managed\"\n              ? \"AI 托管\"\n              : conversationMode === \"human_managed\"\n                ? \"人工接管\"\n                : \"已暂停\"",

    # MessagePanel.tsx - placeholder
    "isPaused\n                ? \"��������ͣ\"\n                : conversationMode === \"human_managed\"\n                  ? \"������������...(Enter����)\"\n                  : \"������Ϣ...(Enter����)\"": "isPaused\n                ? \"聊天已暂停\"\n                : conversationMode === \"human_managed\"\n                  ? \"输入消息发送...(Enter发送)\"\n                  : \"输入消息...(Enter发送)\"",

    # MessagePanel.tsx - preview text fallback
    "{preview || \"������Ϣ\"}": "{preview || \"暂无消息\"}",

    # QuickToolbar.tsx
    "{ label: \"����ʾ��\", text: \"hola, mi pedido no ha llegado\", lang: \"es\" }": "{ label: \"西语示例\", text: \"hola, mi pedido no ha llegado\", lang: \"es\" }",
    "{ label: \"����ʾ��\", text: \"bonjour, je veux modifier ma commande\", lang: \"fr\" }": "{ label: \"法语示例\", text: \"bonjour, je veux modifier ma commande\", lang: \"fr\" }",
    "{ label: \"����ʾ��\", text: \"������������ѯ��������\", lang: \"zh-CN\" }": "{ label: \"中文示例\", text: \"你好我想查询我的订单\", lang: \"zh-CN\" }",

    # CustomerTab.tsx
    "δѡ������": "未选择会话",
    "δ��������������": "未加载客户资料",
    "\"��ת����ҳ\"": "\"跳转客户页\"",
    "��ת����ҳ": "跳转客户页",
    "δ����": "未设置",
    "����": "暂无",
    "δ֪": "未知",
    "��ǰ����δ��������������": "当前会话未关联客户资料",
    "������֤��¼": "暂无验证记录",
    "������...": "加载中...",
    "����������¼": "暂无绑定记录",
    "��Ա��֤": "会员验证",
    "��Ա��֤״̬": "会员验证状态",
    "WhatsApp ����": "WhatsApp 绑定",
    "���� ID": "用户 ID",
    "����": "昵称",
    "״̬": "状态",
    "����": "类型",
    "����ʱ��": "最后时间",
    "��ע": "备注",
    "ʧ��ԭ��": "失败原因",
    "��������": "绑定手机",

    # DetailTab.tsx
    "AI ����": "AI 托管",
    "AI ״̬": "AI 状态",
    "ȫ�� AI": "全局 AI",
    "���� AI": "账号 AI",
    "���� AI": "会话 AI",
    "��������": "人工接管",
    "��ͣ": "暂停",
    "������": "已启用",
    "������": "已禁用",
    "ԭ��": "原因",
    "����": "会话",
    "����ģʽ": "管理模式",
    "���� ID": "号码 ID",
    "����": "客户",
    "������Ϣ": "最后消息",
    "��������": "接管状态",
    "����ת����": "建议转人工",
    "��ͨ����": "普通消息",
    "����ԭ��": "接管原因",
    "������ϯ": "当前坐席",
    "δ����": "未分配",
    "δѡ������": "未选择会话",
    "δ֪": "未知",
    "fmt(v) : \"����\"": "fmt(v) : \"暂无\"",

    # OperationsTab.tsx
    "δѡ������": "未选择会话",
    "AI ����": "AI 托管",
    "��������": "人工接管",
    "��ͣ": "暂停",
    "δ֪": "未知",
    "AI ����": "AI 控制",
    "ȫ�� AI: {globalAiEnabled ? \"����\" : \"����\"}": "ȫ�� AI: {globalAiEnabled ? \"已开\" : \"已关\"}",
    "���� AI: {conversation.ai_enabled ? \"����\" : \"����\"}": "会话 AI: {conversation.ai_enabled ? \"已开\" : \"已关\"}",
    "ȫ�� AI ������": "全局 AI 已关闭",
    "ѡ��������ϯ": "选择操作坐席",
    "ԭ������ѡ��": "输入原因(可选)",
    "ȷ����������": "确认人工接管",
    "ȷ������ AI": "确认恢复 AI",
    "ȷ����ͣ����": "确认暂停会话",
    "ȷ����������": "确认关闭会话",
    "ȷ���������� AI": "确认切换会话 AI",
    "��������": "人工接管",
    "���� AI": "恢复 AI",
    "��ͣ����": "暂停会话",
    "��������": "关闭会话",
    "�������� AI": "关闭会话 AI",
    "�������� AI": "开启会话 AI",
    "ȷ������": "确认接管",
    "ȡ��": "取消",
    "ȷ����ͣ": "确认暂停",
    "ȷ������": "确认关闭",
    "ȷ��": "确认",
    "���˽�����": "建议转人工",

    # HistoryTab.tsx
    "������ʷ": "接管的操作履历",
    "��������": "接管操作",
    "ȫ��ʱ����": "全时操作履历",
    "ȫ��ʱ���������� {Math.min(timeline.length, 20)} ����": "全时操作履历(最近 {Math.min(timeline.length, 20)} 条)",
    "ģ��������־": "模板消息发送日志",
    "ģ��������־������ {Math.min(templateLogs.length, 10)} ����": "模板消息发送日志(最近 {Math.min(templateLogs.length, 10)} 条)",
    "������ʷ��¼": "暂无操作记录",
    "��Ϣ����": "消息事件",
    "��������": "审计事件",
}

def fix_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    original = content
    for corrupted, correct in FIXES.items():
        if corrupted in content:
            content = content.replace(corrupted, correct)

    if content != original:
        with open(filepath, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        print(f"FIXED: {os.path.basename(filepath)}")
        return True
    return False

# Fix all admin-chat files
fixed = 0
for fname in os.listdir(CHAT_DIR):
    if fname.endswith(".tsx"):
        fpath = os.path.join(CHAT_DIR, fname)
        if fix_file(fpath):
            fixed += 1

print(f"\nFixed {fixed} files")
