"""第二轮修复：使用 Latin-1 回环 + 更多映射"""
import os, re

CHAT_DIR = r"e:\codex\WhatsApp\frontend\src\pages\admin-chat"

# Try Latin-1 recovery: encode as Latin-1 bytes, decode as UTF-8
def try_latin1_recovery(text):
    """Try to recover Chinese by encoding Latin-1 chars back to bytes and decoding as UTF-8"""
    try:
        # Only process characters in Latin-1 range (0-255)
        bytes_list = []
        for ch in text:
            cp = ord(ch)
            if 0x80 <= cp <= 0xFF:
                bytes_list.append(cp)
        if not bytes_list:
            return None
        recovered = bytes(bytes_list).decode('utf-8')
        return recovered
    except:
        return None

# Try GBK recovery
def try_gbk_recovery(text):
    """Try GBK round-trip for stray corrupted text"""
    try:
        gbk_bytes = text.encode('gbk')
        recovered = gbk_bytes.decode('utf-8')
        return recovered
    except:
        return None

# More corrupt->correct mappings
EXTRA_FIXES = {
    # CustomerTab.tsx
    "客户客户��Ҫ": "客户基本信息",
    "客户��...": "加载中...",
    "客户ʱ��": "最后时间",
    "客户客户��¼": "暂无验证记录",
    "客户客户��": "暂无绑定",
    "��ǰ客户未加载客户资料": "当前会话未关联客户资料",
    
    # DetailTab.tsx
    "客户��Ч��AI 客户��": "当前生效中: AI 自动回复",
    "客户客户��${status.primary_blocking_reason.message}": "被阻止: ${status.primary_blocking_reason.message}",
    "客户客户��${status.blocking_reasons[0].message}": "被阻止: ${status.blocking_reasons[0].message}",
    "客户��": "进行中",
    "客户ת客户": "建议转人工",
    "客户��ϯ": "当前坐席",
    "客户��Ϣ": "最后消息",
    "客户客户客户": "当前无法确认",
    
    # MessagePanel.tsx
    "客户客户��": "消息列表",
    "��Ϣ��": "消息区",
    "客户��Ϣ": "条新消息",
    
    # OperationsTab.tsx
    "ԭ客户��ѡ��": "输入原因(可选)",
    "ȷ客户客户��": "确认人工接管",
    "ȷ客户�� AI": "确认恢复 AI",
    "ȷ客户ͣ客户": "确认暂停会话",
    "ȷ客户客户": "确认关闭",
    "暂停ֹ客户": "已暂停，AI 已停止",
    "客户客户客户Ϣ": "关闭后无法继续发送消息",
    "ȡ��": "取消",
    "客户客户��": "已暂停",
    "客户客户客户": "无法验证",
    "暂停�� AI 客户客户客户客户": "暂停后 AI 不会自动回复",
    "客户客户客户暂停": "关闭后 AI 被",
    "客户客户�� AI 客户": "恢复后 AI 会自",
    "全局 AI 客户��": "全局 AI 已关闭",
    "客户客户客户客户Ϣ": "继续发送消息",
    "AI 暂停ֹ客户": "AI 暂停回复",
    "确认客户客户": "确认关闭",
    "确认客户ͣ": "确认暂停",
    "确认客户": "确认",
    "确认客户��": "确认关闭",
    
    # QuickToolbar.tsx
    "ѡ��ģ��": "选择模板",
    "ѡ��ý��": "选择媒体",
    "客户ֵ": "填入变量值",
    "ʾ客户��": "示例变量",
    "客户ģ��": "发送模板",
    "客户ý��": "发送媒体",
    "Ӣ�� (en)": "英语 (en)",
    "Caption (��ѡ)": "Caption (可选)",
    "客户�� (��ѡ)": "文件名 (可选)",
    "ÿ�� key=value": "每行一个 key=value",
    
    # HistoryTab.tsx
    "��Ϣ客户": "消息事件",
    "客户��ʷ": "接管历史",
    "ȫ��ʱ客户": "全量时间线",
    "ȫ��ʱ客户客户��": "全量时间线(最近",
    "客户": "条)",
    "ģ客户客户־客户��": "模板日志(最近",
    "客户��ʷ��¼": "暂无操作记录",
    
    # ConversationList.tsx
    "客户��...": "加载中...",
}

def fix_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    original = content
    
    # Apply extra fixes
    for corrupted, correct in EXTRA_FIXES.items():
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
for fname in sorted(os.listdir(CHAT_DIR)):
    if fname.endswith(".tsx"):
        fpath = os.path.join(CHAT_DIR, fname)
        if fix_file(fpath):
            fixed += 1

print(f"\nFixed {fixed} files")
