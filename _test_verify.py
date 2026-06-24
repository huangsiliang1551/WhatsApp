"""验证所有后端端点和修复是否正常工作"""
import httpx, asyncio

async def main():
    async with httpx.AsyncClient() as client:
        r = await client.post('http://localhost:8000/api/admin/auth/login', json={'username':'admin','password':'admin123'})
        token = r.json()['access_token']
        headers = {
            'Authorization': f'Bearer {token}',
            'X-Actor-Id': 'agent-cn-console',
            'X-Actor-Name': 'Admin',
            'X-Actor-Role': 'super_admin',
            'X-Actor-Account-Ids': 'account-1',
        }
        
        print("=== 验证修复 ===")
        print()
        
        tests = [
            # 通知 API
            ('GET', '/api/notifications?limit=1&unread=true', '通知API(新)'),
            # H5 认证
            ('GET', '/api/h5/auth/me', 'H5认证(401预期)'),
            # 会话轮询
            ('GET', '/api/conversations', '会话列表'),
            # 模板
            ('GET', '/api/templates', '模板列表'),
            ('GET', '/api/templates/send-logs?limit=5', '模板发送日志(注意DB)'),
            # 崩溃页面依赖
            ('GET', '/api/whatsapp/stats/detail?limit=5', 'WhatsApp统计'),
            ('GET', '/api/runtime/audit-logs?limit=5', '审计日志'),
            ('GET', '/api/runtime/config-summary', '运行时配置'),
            ('GET', '/api/platform/sites', '站点列表'),
            # 工作台
            ('GET', '/api/meta/accounts', 'Meta账户'),
            ('GET', '/api/runtime/state', '运行时状态'),
            # 审核/工单/客户
            ('GET', '/api/reviews/queue', '审核队列'),
            ('GET', '/api/tickets', '工单'),
            ('GET', '/api/platform/users', '平台用户'),
            # API/Webhook
            ('GET', '/api/runtime/provider-status-buffer', '状态缓冲'),
        ]
        
        passed = 0
        failed = 0
        for method, path, desc in tests:
            try:
                if method == 'GET':
                    resp = await client.get(f'http://localhost:8000{path}', headers=headers, timeout=10)
                status = resp.status_code
                if status >= 500:
                    print(f"  [500] {desc}: {path}")
                    failed += 1
                elif status in (401, 404):
                    if 'H5认证' in desc and status == 401:
                        print(f"  [OK] {desc}: (401预期)")
                        passed += 1
                    else:
                        print(f"  [{status}] {desc}: {path}")
                        failed += 1
                else:
                    print(f"  [OK] {desc}")
                    passed += 1
            except Exception as e:
                print(f"  [ERR] {desc}: {e}")
                failed += 1
        
        print()
        print(f"总计: {passed} OK, {failed} 失败")

asyncio.run(main())
