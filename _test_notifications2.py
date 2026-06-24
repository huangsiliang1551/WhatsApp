import httpx, asyncio

async def main():
    async with httpx.AsyncClient() as client:
        r = await client.post('http://localhost:8000/api/admin/auth/login', json={'username':'admin','password':'admin123'})
        token = r.json()['access_token']
        
        # Test notifications WITHOUT Actor headers (like the frontend poller does)
        headers = {'Authorization': f'Bearer {token}'}
        r = await client.get('http://localhost:8000/api/notifications?limit=1&unread=true', headers=headers)
        print(f'No Actor headers: {r.status_code} - {r.text[:100]}')

        # Test with minimal Actor headers
        headers2 = {
            'Authorization': f'Bearer {token}',
            'X-Actor-Id': 'admin',
            'X-Actor-Name': 'Admin',
            'X-Actor-Role': 'super_admin',
            'X-Actor-Account-Ids': 'account-1',
        }
        r = await client.get('http://localhost:8000/api/notifications?limit=1&unread=true', headers=headers2)
        print(f'Actor headers: {r.status_code} - {r.text[:100]}')

asyncio.run(main())
