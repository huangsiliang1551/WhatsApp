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
        
        # Test notifications
        r = await client.get('http://localhost:8000/api/notifications', headers=headers)
        print(f'Notifications: {r.status_code}')
        print(f'Body: {r.text[:200]}')
        
        # Test notifications with params
        r = await client.get('http://localhost:8000/api/notifications?limit=1&unread=true', headers=headers)
        print(f'Notifications (unread): {r.status_code}')
        print(f'Body: {r.text[:200]}')

asyncio.run(main())
