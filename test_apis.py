import urllib.request
import json

BASE_URL = "http://localhost:5000"

def test_api():
    print("Testing API endpoints...")
    
    # 2. Confirm per-node config API works
    print("\n1. Testing POST /api/admin/node_config/HASH-1")
    req = urllib.request.Request(f'{BASE_URL}/api/admin/node_config/HASH-1', data=json.dumps({'person_conf': 0.45, 'canny_low': 60, 'canny_high': 180}).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
    res = urllib.request.urlopen(req).read().decode('utf-8')
    print("Response:", res)
    
    print("\n2. Testing GET /api/admin/node_config/HASH-1")
    req = urllib.request.Request(f'{BASE_URL}/api/admin/node_config/HASH-1', method='GET')
    res = urllib.request.urlopen(req).read().decode('utf-8')
    print("Response:", res)
    
    # 3. Confirm telemetry API works
    print("\n3. Testing GET /api/admin/telemetry")
    req = urllib.request.Request(f'{BASE_URL}/api/admin/telemetry', method='GET')
    res = urllib.request.urlopen(req).read().decode('utf-8')
    print("Response:", res)
    
    # 4. Confirm simulate threat still works
    print("\n4. Testing POST /api/admin/simulate_threat/HASH-1")
    req = urllib.request.Request(f'{BASE_URL}/api/admin/simulate_threat/HASH-1', method='POST')
    res = urllib.request.urlopen(req).read().decode('utf-8')
    print("Response:", res)
    
    # 5. Confirm clear background works
    print("\n5. Testing POST /api/admin/clear_bg/HASH-1")
    req = urllib.request.Request(f'{BASE_URL}/api/admin/clear_bg/HASH-1', method='POST')
    res = urllib.request.urlopen(req).read().decode('utf-8')
    print("Response:", res)

if __name__ == "__main__":
    try:
        test_api()
        print("\nAll tests ran successfully.")
    except Exception as e:
        print(f"\nError running tests: {e}")
