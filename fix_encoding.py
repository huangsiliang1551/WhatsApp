import os, re, sys

pages_dir = r"E:\codex\WhatsApp\frontend\src\pages"

# List all tsx files in pages dir
for f in sorted(os.listdir(pages_dir)):
    if not f.endswith('.tsx') or f in ['DashboardPage.tsx', 'ChatPage.tsx']:
        continue
    
    path = os.path.join(pages_dir, f)
    
    # Read file bytes
    with open(path, 'rb') as fh:
        raw = fh.read()
    
    # Try to decode as utf-8 first
    try:
        content = raw.decode('utf-8')
    except UnicodeDecodeError:
        # If utf-8 fails, the file was corrupted. 
        # Try reading with utf-8-sig or other encodings
        content = raw.decode('utf-8', errors='replace')
    
    # Check if this file has the AdminDataSourceLegend import
    import_pattern = r'import { AdminDataSourceLegend } from "../components/AdminDataSourceLegend";\s*\n?'
    
    if re.search(import_pattern, content):
        # Remove import
        content = re.sub(import_pattern, '', content)
        # Remove admin datasource legend usage (single line)
        content = re.sub(r'<AdminDataSourceLegend[^>]*/>\s*\n?', '', content)
        
        # Check for garbled Chinese chars and fix
        garbled_map = {
            '鏄': '是', '鍚': '否', '鏆': '暂', '傛': '无',
            '鎺': '接', '鏃': '时', '堕': '间', '挎': '控',
            '寮': '开', '惎': '启', '鐢': '用', '镐': '高',
            '绠': '管', '悊': '理', '椤': '页', '数': '数',
            '椤圭洰': '项目', '鏄庯細': '说明:',
            '闈': '面', '璁': '认', '璇': '证', '璇佺ず': '证书',
            '璁よ瘉': '认证', '璁よ瘉鏍': '认证状',
            '鎵ц': '执行', '鎵ц': '执行', '缁': '组',
            '缁戝畾': '绑定', '缁戝畬': '绑定完',
            '蹇界暐': '忽略', '椹卞姩': '驱动',
            '璇锋眰': '请求', '璇锋眰鏁版嵁': '请求数据',
            '鏂规': '方案', '鏂规': '方案', '鎺ㄨ崘': '推荐',
            '鎺ㄨ獙': '推荐', '鐩戞帶': '监控',
            '鏃堕棿': '时间', '鏃堕棿鎴': '时间戳',
            '璇︽儏': '详情', '璇︽殏': '详情',
            '鏃犳晥': '无效', '鏈夋晥': '有效',
            '鎵�': '所', '鎵嬫満': '手机', '鍙风爜': '号码',
            '鐧婚檰': '登录', '瑙勫垯': '规则',
            '璁剧疆': '设置', '宸茬煡': '已知',
            '鏈�': '最', '鏂扮増': '新版', '鑱婂ぉ': '聊天',
            '瀹㈡埛': '客户', '鏁版嵁': '数据',
            '鐧婚檰璁よ瘉': '登录认证',
            '鐢佃瘽': '电话',
            '瓒呰繃': '超过',
            '浼樺厛': '优先',
            '淇℃伅': '信息',
            '瀛樺偍': '存储',
            '鏍煎紡': '格式',
            '瓒呰繃闄愬埗': '超过限制',
            '淇濆瓨': '保存',
            '鏂板': '新增',
            '缂栬緫': '编辑',
            '琚�': '被',
            '瀵艰嚧': '导致',
            '璇疯緭鍏': '请输入',
            '璇疯緭鍏ュ旀墭浜': '请输入委托人',
            '璇锋坊鍔': '请添加',
            '鐢宠': '申请',
            '璁㈠崟': '订单',
            '浠诲姟': '任务',
            '鏍规嵁': '根据',
            '缃戠粶': '网络',
            '閿欒': '错误',
            '鎴愬姛': '成功',
            '澶辫触': '失败',
            '姝ｅ湪': '正在',
            '澶勭悊': '处理',
            '鏍囪': '标记',
            '鎸傝捣': '挂起',
            '鎮ㄧ殑': '您的',
            '璁㈠崟鏁伴噺': '订单数量',
            '鎺ラ攢': '接口',
            '绯荤粺': '系统',
            '鐜': '环境',
            '閰嶇疆': '配置',
            '淇敼': '修改',
            '鍒犻櫎': '删除',
            '娣诲姞': '添加',
            '鏌ョ湅': '查看',
            '鎼滅储': '搜索',
            '浼樺厛绾': '优先级',
            '鐘舵��': '状态',
            '宸茬粡': '已经',
            '鏈煡': '未知',
            '鏄庣伒': '灵敏',
            '鎺ㄨ崘绛夌骇': '推荐等级',
        }
        
        for garbled, correct in sorted(garbled_map.items(), key=lambda x: -len(x[0])):
            content = content.replace(garbled, correct)
        
        # Write back with UTF-8 encoding (no BOM)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(content)
        print(f"✓ Fixed {f}")
    else:
        print(f"  Skipped {f} (no AdminDataSourceLegend)")
