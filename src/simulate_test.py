"""
simulate_and_test.py — Full acknowledge cycle test script.
Simulates a threat on a node, waits for it to appear in /api/threats/active,
acknowledges it, then verifies it clears from active threats AND from analyze/all.
"""
import requests
import time
import json

BASE = "http://localhost:5000"

def get(path):
    r = requests.get(BASE + path, timeout=5)
    if r.status_code == 200:
        return r.json()
    return {"error": r.status_code, "text": r.text[:200]}

def post(path, data=None, auth=True):
    headers = {"Authorization": "Bearer admin_test"} if auth else {}
    r = requests.post(BASE + path, json=data or {}, headers=headers, timeout=5)
    return r.status_code, r.text[:200]

def trigger_instant_alarm(node_id):
    """Directly trigger an instant alarm via the backend's trigger_instant_alarm method."""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    from hashtag_v2_backend import get_system
    from detection_engine import Detection
    sys_obj = get_system()
    fake_det = Detection(x=100, y=100, w=200, h=300, confidence=0.99,
                         class_name="Person", source="test", keypoints=None, metadata={})
    sys_obj.trigger_instant_alarm(node_id, [fake_det], from_inference=True)
    print(f"[TEST] Fired instant alarm on {node_id}")

def check_threats():
    d = get("/api/threats/active")
    return d if isinstance(d, list) else []

def check_jobs():
    d = get("/api/analyze/all")
    if isinstance(d, dict):
        return d.get("jobs", [])
    return []

def acknowledge(node_id):
    status, text = post(f"/api/admin/acknowledge/{node_id}")
    print(f"[TEST] Acknowledge {node_id}: HTTP {status} | {text[:80]}")
    return status == 200

def run_test(node_id, label):
    print(f"\n{'='*60}")
    print(f"TEST: {label} ({node_id})")
    print(f"{'='*60}")

    # Step 1: Check baseline
    threats = check_threats()
    pre_threats = [t for t in threats if t["node_id"] == node_id]
    print(f"[TEST] Pre-test threats for {node_id}: {pre_threats}")

    # Step 2: Trigger alarm
    trigger_instant_alarm(node_id)
    time.sleep(0.5)

    # Step 3: Confirm alarm appeared
    threats = check_threats()
    active = [t for t in threats if t["node_id"] == node_id]
    print(f"[TEST] After trigger threats: {active}")
    if not active:
        print(f"[FAIL] Threat did not appear in /api/threats/active!")
        return False

    # Step 4: Check jobs
    jobs = check_jobs()
    node_jobs = [j for j in jobs if j.get("node_id") == node_id]
    print(f"[TEST] Jobs for node: {len(node_jobs)}")
    for j in node_jobs:
        print(f"       job={j.get('job_id','?')[:20]} ack={j.get('acknowledged')} auto={j.get('is_auto_trigger')} threat={j.get('threat_detected')}")

    # Step 5: Acknowledge
    if not acknowledge(node_id):
        print(f"[FAIL] Acknowledge call failed!")
        return False
    time.sleep(0.5)

    # Step 6: Verify cleared from threats/active
    threats = check_threats()
    still_active = [t for t in threats if t["node_id"] == node_id]
    if still_active:
        print(f"[FAIL] Threat still in /api/threats/active after acknowledge: {still_active}")
        result1 = False
    else:
        print(f"[PASS] /api/threats/active is clear for {node_id}")
        result1 = True

    # Step 7: Verify jobs are marked acknowledged
    jobs = check_jobs()
    node_jobs = [j for j in jobs if j.get("node_id") == node_id]
    unack_jobs = [j for j in node_jobs if not j.get("acknowledged") and j.get("is_auto_trigger")]
    if unack_jobs:
        print(f"[FAIL] {len(unack_jobs)} unacknowledged auto-trigger jobs still exist!")
        for j in unack_jobs:
            print(f"       {j.get('job_id','?')[:20]} ack={j.get('acknowledged')}")
        result2 = False
    else:
        print(f"[PASS] All auto-trigger jobs for {node_id} are acknowledged")
        result2 = True

    # Step 8: Wait 2s and re-check that no new threats appeared
    time.sleep(2.0)
    threats = check_threats()
    still_active = [t for t in threats if t["node_id"] == node_id]
    if still_active:
        print(f"[FAIL] Threat re-appeared 2s after acknowledge! {still_active}")
        result3 = False
    else:
        print(f"[PASS] No re-alarm after 2s for {node_id}")
        result3 = True

    return result1 and result2 and result3

if __name__ == "__main__":
    print("Hashtag V2 — Acknowledge Cycle Test")
    print("Checking /api/analyze/all first...")
    
    # Diagnose the 500 first
    try:
        jobs = check_jobs()
        print(f"analyze/all OK — {len(jobs)} jobs")
    except Exception as e:
        print(f"analyze/all FAILED: {e}")

    r1 = run_test("HASH-3", "RPi GStreamer (DETECTION)")
    r2 = run_test("HASH-1781781956572", "BP74 (PIR)")
    r3 = run_test("HASH-1", "Tiger Chongjang (PIR)")

    print(f"\n{'='*60}")
    print(f"RESULTS:")
    print(f"  RPi GStreamer : {'PASS' if r1 else 'FAIL'}")
    print(f"  BP74          : {'PASS' if r2 else 'FAIL'}")
    print(f"  TigerChongjang: {'PASS' if r3 else 'FAIL'}")
    print(f"{'='*60}")
