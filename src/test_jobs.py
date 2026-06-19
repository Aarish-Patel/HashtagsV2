import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from hashtag_v2_backend import get_system, AnalysisJob

sys_obj = get_system()

print(f"Total jobs: {len(sys_obj._jobs)}")
print(f"Active threats:")
for nid, node in sys_obj.nodes.items():
    print(f"  {nid} ({node.name}): threat_count={node._active_threat_count}")

print("\nJobs:")
with sys_obj._job_lock:
    items = list(sys_obj._jobs.items())[-20:]

for jid, job in items:
    try:
        d = job.get_status_dict()
        print(f"  {jid[:20]}: ack={d.get('acknowledged')} auto={d.get('is_auto_trigger')} threat={d.get('threat_detected')} node={d.get('node_id')}")
    except Exception as e:
        print(f"  ERROR on {jid}: {e}")
        traceback.print_exc()

print("\nTesting analyze/all serialization...")
try:
    import json
    recent_jobs = []
    with sys_obj._job_lock:
        for jid, job in list(sys_obj._jobs.items())[-20:]:
            recent_jobs.append(job.get_status_dict())
    s = json.dumps({"jobs": recent_jobs})
    print(f"Serialization OK: {len(recent_jobs)} jobs, {len(s)} bytes")
except Exception as e:
    print(f"SERIALIZATION ERROR: {e}")
    traceback.print_exc()
