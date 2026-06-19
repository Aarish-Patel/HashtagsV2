"""
Full acknowledge cycle test using the live Flask server.
Tests: trigger_instant_alarm → threats/active shows threat → acknowledge → cleared → no re-alarm
"""
import requests, time, json

BASE = "http://localhost:5000"
H = {"Authorization": "disabled"}

def get_threats():
    return requests.get(BASE+"/api/threats/active", headers=H, timeout=5).json()

def get_jobs():
    r = requests.get(BASE+"/api/analyze/all", headers=H, timeout=5)
    if r.status_code == 200:
        return r.json().get("jobs", [])
    return []

def ack(node_id):
    r = requests.post(BASE+f"/api/admin/acknowledge/{node_id}", headers=H, timeout=5)
    return r.status_code, r.json()

def trigger_instant(node_id):
    """Fire instant alarm directly via the backend's trigger_instant_alarm."""
    # Use the simulate endpoint which internally builds a fake detection
    # But also use the direct instant alarm path via a helper route
    r = requests.post(BASE+f"/api/admin/trigger_instant/{node_id}", headers=H, timeout=5)
    if r.status_code == 404:
        # Fallback: use simulate_threat and wait for batch
        r2 = requests.post(BASE+f"/api/admin/simulate_threat/{node_id}", headers=H, timeout=5)
        return r2.status_code, r2.json()
    return r.status_code, r.json()

def run_test(node_id, label):
    print(f"\n{'='*55}")
    print(f"TEST: {label}")
    print(f"{'='*55}")
    
    # Clear any pre-existing alerts for this node
    threats_before = [t for t in get_threats() if t["node_id"] == node_id]
    if threats_before:
        print(f"  Clearing pre-existing threats: {threats_before[0]['threat_count']}")
        ack(node_id)
        time.sleep(0.3)

    # Step 1: Verify clean state
    threats = [t for t in get_threats() if t["node_id"] == node_id]
    print(f"  [1] Pre-test threats: {threats}")
    
    # Step 2: Fire instant alarm via acknowledge endpoint on backend (direct backend call)
    # We'll inject an instant alarm directly through the Flask API
    # Since there's no /api/admin/trigger_instant, we'll call simulate_threat
    # and also check if the instant path via the direct API works
    print(f"  [2] Firing alarm via simulate_threat...")
    r = requests.post(BASE+f"/api/admin/simulate_threat/{node_id}", headers=H, timeout=5)
    print(f"       simulate: {r.status_code} {r.text[:60]}")
    
    # Also force an instant alarm directly via a hidden test endpoint
    # Check if threat appeared quickly (instant path)
    time.sleep(0.5)
    threats = [t for t in get_threats() if t["node_id"] == node_id]
    print(f"  [3] After 0.5s: {len(threats)} threat(s) for {node_id}")
    
    if not threats:
        # simulate_threat requires frames in the buffer. Use direct backend manipulation.
        print(f"       No frames in buffer, injecting instant alarm via direct call...")
        # Try the trigger_instant endpoint
        r2 = requests.post(BASE+f"/api/admin/instant_alarm/{node_id}", headers=H, timeout=5)
        if r2.status_code != 200:
            print(f"       No instant_alarm endpoint ({r2.status_code}), skipping alarm injection")
            print(f"  [SKIP] Cannot inject alarm without stream buffer - test inconclusive")
            return "SKIP"
        time.sleep(0.5)
        threats = [t for t in get_threats() if t["node_id"] == node_id]
    
    if not threats:
        print(f"  [FAIL] Could not inject threat for {node_id}")
        return False

    threat_count = threats[0]["threat_count"]
    print(f"  [3] Threat confirmed: count={threat_count}")
    
    # Step 4: Acknowledge
    status, resp = ack(node_id)
    print(f"  [4] Acknowledge: HTTP {status} | {resp}")
    time.sleep(0.5)
    
    # Step 5: Verify cleared
    threats = [t for t in get_threats() if t["node_id"] == node_id]
    if threats:
        print(f"  [FAIL] Threat still active after acknowledge: count={threats[0]['threat_count']}")
        return False
    print(f"  [5] Threats cleared OK")
    
    # Step 6: Check jobs are acknowledged
    jobs = get_jobs()
    node_jobs = [j for j in jobs if j.get("node_id") == node_id and j.get("is_auto_trigger")]
    unack = [j for j in node_jobs if not j.get("acknowledged")]
    if unack:
        print(f"  [FAIL] {len(unack)} unacknowledged auto-jobs still visible!")
        for j in unack:
            print(f"         {j.get('job_id','?')[:20]} threat={j.get('threat_detected')}")
        return False
    print(f"  [6] All auto-trigger jobs acknowledged OK ({len(node_jobs)} total jobs for node)")

    # Step 7: Wait 3s and check no re-alarm
    time.sleep(3.0)
    threats = [t for t in get_threats() if t["node_id"] == node_id]
    if threats:
        print(f"  [FAIL] Threat RE-APPEARED 3s after acknowledge! count={threats[0]['threat_count']}")
        return False
    print(f"  [7] No re-alarm after 3s - PASS")
    
    return True

if __name__ == "__main__":
    print("Hashtag V2 — Full Acknowledge Cycle Test (via live server)")
    print(f"Server: {BASE}")
    
    print("\n--- Checking server state ---")
    threats = get_threats()
    print(f"Active threats: {[(t['node_id'], t['threat_count']) for t in threats]}")
    jobs = get_jobs()
    print(f"Existing jobs: {len(jobs)}")
    
    # Clear all stale threats first
    if threats:
        print("\nClearing all stale threats...")
        for t in threats:
            s, r = ack(t["node_id"])
            print(f"  Ack {t['node_id']}: {s}")
        time.sleep(1)

    results = {}
    for node_id, label in [
        ("HASH-3",              "RPi GStreamer TCP (DETECTION)"),
        ("HASH-1781781956572",  "BP74 (PIR)"),
        ("HASH-1",              "Tiger Chongjang (PIR)"),
    ]:
        results[label] = run_test(node_id, label)

    print(f"\n{'='*55}")
    print("FINAL RESULTS:")
    for label, result in results.items():
        status = "PASS" if result is True else ("SKIP" if result == "SKIP" else "FAIL")
        print(f"  {status}  {label}")
    print(f"{'='*55}")
