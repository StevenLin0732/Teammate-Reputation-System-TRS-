import requests
import random
import sys

API_BASE = 'http://localhost:5000'

s = requests.Session()

email = f"testuser{random.randint(1000,9999)}@duke.edu"
password = "password123"
name = "Test User"

print('Creating user:', email)
resp = s.post(f"{API_BASE}/api/users", json={"name": name, "email": email, "password": password})
print('Create user status:', resp.status_code)
try:
    print('Create response:', resp.json())
except Exception:
    print('Create response text:', resp.text)

if resp.status_code not in (200, 201):
    print('Failed to create user, aborting')
    sys.exit(2)

# Try logging in with JSON
headers = {"Accept": "application/json"}
print('\nLogging in via JSON to /login')
resp = s.post(f"{API_BASE}/login", json={"email": email, "password": password}, headers=headers)
print('Login status:', resp.status_code)
try:
    print('Login response:', resp.json())
except Exception:
    print('Login response text:', resp.text)

# Fetch /me
print('\nFetching /me')
resp = s.get(f"{API_BASE}/me", headers=headers)
print('/me status:', resp.status_code)
try:
    print('/me json:', resp.json())
except Exception:
    print('/me text:', resp.text)

# Check if session cookie present
cookies = s.cookies.get_dict()
print('\nSession cookies in session:', cookies)

if resp.status_code == 200 and resp.headers.get('Content-Type','').startswith('application/json'):
    print('\nSUCCESS: API login flow works and /me returned JSON.')
    sys.exit(0)
else:
    print('\nFAILED: /me did not return JSON 200. Check server logs and CORS/session configuration.')
    sys.exit(3)
