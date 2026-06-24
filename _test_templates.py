import httpx, asyncio, json

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
        
        r = await client.get('http://localhost:8000/api/templates/send-logs?limit=5', headers=headers, timeout=10)
        print(f'Status: {r.status_code}')
        if r.status_code >= 400:
            print(f'Body: {r.text}')
        else:
            data = r.json()
            print(f'Items: {len(data) if isinstance(data, list) else "not a list"}')
            if isinstance(data, list):
                for item in data[:2]:
                    print(json.dumps(item, ensure_ascii=False)[:200])
        
        # Also check template service
        print("\n--- Checking template_service ---")
        try:
            r2 = await client.get('http://localhost:8000/api/templates?limit=1', headers=headers, timeout=10)
            print(f'Templates list: {r2.status_code}')
            print(f'Body: {r2.text[:300]}')
        except Exception as e:
            print(f'Templates error: {e}')

asyncio.run(main())
