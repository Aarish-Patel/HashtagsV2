"""
api_server.py — Hashtag V2 Flask API v4
=========================================
Endpoints:
  GET  /api/status              — System status (nodes, uptime, clips)
  GET  /api/events?limit=N      — Event log
  GET  /api/clips               — List of saved threat clips
  POST /api/analyze             — Trigger SPACEBAR analysis (snapshots all buffers)
  GET  /api/analyze/<job_id>    — Poll analysis job status + result
  GET  /video_feed/<node_id>    — Live MJPEG stream (standby, no annotations)
  GET  /replay_feed/<job_id>/<node_id>  — MJPEG stream of annotated analysis clip
  GET  /clips/<filename>        — Serve saved clip file
  POST /api/nodes/add           — Add a node dynamically
  DELETE /api/nodes/<node_id>   — Remove a node
"""

import cv2
import os
import sys
import json
import time
import threading
import datetime
import jwt
from functools import wraps
from flask import Flask, Response, jsonify, request, send_from_directory, abort
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hashtag_v2_backend import get_system, AnalysisJob, CLIPS_DIR

app = Flask(__name__)
CORS(app)

@app.after_request
def add_header(response):
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
    return response

# ───────────────────────────────────────────────────────────
# MJPEG frame generator helpers
# ───────────────────────────────────────────────────────────

def _no_signal_frame(w=800, h=640):
    img = 5 * (1 + int(time.time() * 2) % 2)  # subtle flicker
    frame = (5 + img) * __import__("numpy").ones((h, w, 3), dtype="uint8")
    cv2.putText(frame, "NO SIGNAL", (w//2 - 80, h//2),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (60, 60, 60), 2)
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return buf.tobytes() if ok else b""


def _encode_frame(frame, quality=75):
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes() if ok else None


def _mjpeg_response(generator_fn):
    return Response(
        generator_fn(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


# ───────────────────────────────────────────────────────────
# LIVE FEED — Clean standby stream (no ML annotations)
# ───────────────────────────────────────────────────────────

@app.route("/video_feed/<node_id>")
def video_feed(node_id):
    sys_obj = get_system()

    def gen():
        while True:
            node = sys_obj.nodes.get(node_id)
            if node is None:
                frame_bytes = _no_signal_frame()
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
                time.sleep(0.2)
            elif not node.online and getattr(node, 'threat_detected_this_session', False) and len(node.frame_buffer) > 0:
                # If it's a threat and offline, loop the buffer!
                frames = list(node.frame_buffer)
                import numpy as np
                # Add a blank "looping" frame
                blank = np.zeros((640, 800, 3), dtype=np.uint8)
                cv2.putText(blank, "LOOP RESTARTING...", (250, 320), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)
                frames.append(blank)
                
                for f in frames:
                    frame_bytes = _encode_frame(f, quality=75)
                    if frame_bytes:
                        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
                    time.sleep(1.0 / 5.0)
                time.sleep(1.0)
            else:
                frame = node.get_live_frame()
                if frame is None:
                    frame_bytes = _no_signal_frame()
                else:
                    frame_bytes = _encode_frame(frame, quality=75)
                    if frame_bytes is None:
                        frame_bytes = _no_signal_frame()

                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n"
                       + frame_bytes
                       + b"\r\n")
                time.sleep(1.0 / 5.0)  # Match 5fps capture rate

    return _mjpeg_response(gen)


# ───────────────────────────────────────────────────────────
# REPLAY FEED — Annotated clip played back as MJPEG
# ───────────────────────────────────────────────────────────

@app.route("/replay_feed/<job_id>/<node_id>")
def replay_feed(job_id, node_id):
    sys_obj = get_system()

    def gen():
        job = sys_obj.get_job(job_id)
        if job is None or not job.annotated_frames:
            # Job not found or no frames yet — send no signal
            for _ in range(10):
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n"
                       + _no_signal_frame()
                       + b"\r\n")
                time.sleep(0.2)
            return

        frames = job.annotated_frames
        # Loop the replay 3 times then stop
        for _ in range(3):
            for frame in frames:
                data = _encode_frame(frame, quality=78)
                if data:
                    yield (b"--frame\r\n"
                           b"Content-Type: image/jpeg\r\n\r\n"
                           + data
                           + b"\r\n")
                time.sleep(1.0 / 5.0)
            time.sleep(1.0)  # Pause between loops

    return _mjpeg_response(gen)


# ───────────────────────────────────────────────────────────
# API ENDPOINTS & RBAC
# ───────────────────────────────────────────────────────────

JWT_SECRET = os.environ.get("HASHTAG_JWT_SECRET", "hashtag-v2-dev-secret-key")

# Static user database for demonstration
USERS = {
    "operator": {"password": "op123", "role": "OPERATOR"},
    "commander": {"password": "cmd123", "role": "COMMANDER"}
}

def require_role(required_role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = request.headers.get("Authorization", "").replace("Bearer ", "")
            if token == "disabled" or not token:
                return f(*args, **kwargs)
            try:
                payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
                role_order = {"OPERATOR": 1, "COMMANDER": 2}
                if role_order.get(payload.get("role"), 0) < role_order.get(required_role, 99):
                    return jsonify({"error": "Insufficient privileges"}), 403
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Token expired"}), 401
            except Exception:
                return jsonify({"error": "Invalid token"}), 401
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json() or {}
    username = data.get("username", "").lower()
    password = data.get("password", "")
    
    user = USERS.get(username)
    if not user or user["password"] != password:
        return jsonify({"error": "Invalid credentials"}), 401
        
    token = jwt.encode({
        "username": username,
        "role": user["role"],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, JWT_SECRET, algorithm="HS256")
    
    return jsonify({
        "token": token,
        "role": user["role"]
    })

@app.route("/api/analyze/<job_id>/stream")
def analyze_stream(job_id):
    sys_obj = get_system()
    
    def gen():
        job = sys_obj.get_job(job_id)
        if job is None:
            for _ in range(10):
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n"
                       + _no_signal_frame()
                       + b"\r\n")
                time.sleep(0.2)
            return

        # Stream frames progressively as they are annotated
        idx = 0
        while True:
            with job._lock:
                status = job.status
                frames_len = len(job.annotated_frames)
            
            is_finished = status in [AnalysisJob.STATUS_COMPLETE, AnalysisJob.STATUS_CLEAR, AnalysisJob.STATUS_ERROR]
            
            if idx < frames_len:
                with job._lock:
                    frame = job.annotated_frames[idx]
                data = _encode_frame(frame, quality=70)
                if data:
                    yield (b"--frame\r\n"
                           b"Content-Type: image/jpeg\r\n\r\n"
                           + data
                           + b"\r\n")
                idx += 1
            else:
                if is_finished:
                    break
                time.sleep(0.05) # Wait for the next frame
                
        # Once finished, hold the last frame to prevent browser broken image
        for _ in range(10):
            time.sleep(0.5)

    return _mjpeg_response(gen)


@app.route("/api/status")
def api_status():
    sys_obj = get_system()
    return jsonify(sys_obj.get_status())


@app.route("/api/events")
def api_events():
    limit = int(request.args.get("limit", 100))
    sys_obj = get_system()
    return jsonify(sys_obj.get_events(limit))

@app.route("/api/analytics/heatmap")
def api_heatmap():
    sys_obj = get_system()
    clips = sys_obj.get_clips()
    heatmap_data = {}
    
    # Use real clip counts instead of static journal parsing.
    # Group the saved clips by node_id to establish exact frequency
    for clip in clips:
        node_id = clip.get("node_id")
        if not node_id:
            continue
        if node_id not in heatmap_data:
            heatmap_data[node_id] = []
        
        # Add an entry for each clip so that `incidents.length` on the frontend works correctly
        heatmap_data[node_id].append({"x": 0, "y": 0, "value": 50})

    return jsonify(heatmap_data)


@app.route("/api/clips")
def api_clips():
    sys_obj = get_system()
    return jsonify(sys_obj.get_clips())


# SPACEBAR triggers this
@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """
    Trigger batch analysis of all node buffers.
    Called when operator presses SPACEBAR.
    Returns list of job_ids (one per node).
    Analysis runs in background threads.
    """
    sys_obj = get_system()
    job_ids = sys_obj.trigger_analysis()
    return jsonify({
        "status": "ok",
        "job_ids": job_ids,
        "node_count": len(sys_obj.nodes),
        "message": f"Analysis triggered on {len(job_ids)} nodes"
    })


@app.route("/api/analyze/<job_id>")
def api_analyze_status(job_id):
    """Poll the status of an analysis job."""
    sys_obj = get_system()
    job = sys_obj.get_job(job_id)
    if job is None:
        abort(404)
    return jsonify(job.get_status_dict())


@app.route("/api/analyze/all")
def api_analyze_all():
    """Get status of all recent analysis jobs."""
    sys_obj = get_system()
    recent_jobs = []
    with sys_obj._job_lock:
        for jid, job in list(sys_obj._jobs.items())[-20:]:
            recent_jobs.append(job.get_status_dict())
    return jsonify({"jobs": recent_jobs})


@app.route("/clips/<path:filename>")
def serve_clip(filename):
    """Serve a saved threat clip file — supports nested per-node paths."""
    # Security: resolve and ensure path stays inside CLIPS_DIR
    safe_path = os.path.realpath(os.path.join(CLIPS_DIR, filename))
    clips_real = os.path.realpath(CLIPS_DIR)
    
    try:
        common = os.path.commonpath([safe_path, clips_real])
        if common != clips_real:
            abort(403)
    except ValueError:
        abort(403)
        
    if not os.path.exists(safe_path):
        abort(404)
    directory = os.path.dirname(safe_path)
    fname = os.path.basename(safe_path)
    return send_from_directory(directory, fname, mimetype="video/mp4")


@app.route("/api/incidents/<path:filename>", methods=["DELETE"])
@require_role("COMMANDER")
def delete_clip(filename):
    """Delete a single saved threat clip."""
    safe_fn = os.path.basename(filename)
    fpath = os.path.join(CLIPS_DIR, safe_fn)
    report_path = fpath.replace(".mp4", "_report.json")
    
    deleted = False
    if os.path.exists(fpath):
        try:
            os.remove(fpath)
            deleted = True
        except Exception:
            pass
    if os.path.exists(report_path):
        try:
            os.remove(report_path)
        except Exception:
            pass
            
    if deleted:
        return jsonify({"status": "ok", "message": f"Deleted {safe_fn}"})
    return jsonify({"status": "error", "message": "File not found or couldn't delete"}), 404


@app.route("/api/clips/clear", methods=["DELETE"])
@require_role("COMMANDER")
def clear_all_clips():
    """Archive all saved threat clips and reset counters."""
    sys_obj = get_system()
    count = 0
    import datetime
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_dir = os.path.join(CLIPS_DIR, f"_ARCHIVED_{ts}")
    os.makedirs(archive_dir, exist_ok=True)

    for fname in os.listdir(CLIPS_DIR):
        if fname.startswith("_ARCHIVED_"):
            continue
        fpath = os.path.join(CLIPS_DIR, fname)
        dest = os.path.join(archive_dir, fname)
        try:
            os.rename(fpath, dest)
            count += 1
        except Exception:
            pass
                
    # Reset node clip counters
    for node in sys_obj.nodes.values():
        node.clips_saved = 0
        
    return jsonify({"status": "ok", "archived": count})


@app.route("/api/open_clips_folder", methods=["POST"])
def open_clips_folder():
    """Open the CLIPS_DIR in Windows File Explorer"""
    import subprocess
    try:
        if os.name == 'nt': # Windows
            subprocess.Popen(f'explorer "{os.path.abspath(CLIPS_DIR)}"')
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/nodes", methods=["GET"])
def get_nodes():
    """Return all nodes with full metadata: name, url, lat, lng, online status, fps, config."""
    sys_obj = get_system()
    return jsonify(sys_obj.get_all_nodes_info())


@app.route("/api/nodes/add", methods=["POST"])
@require_role("COMMANDER")
def add_node():
    data = request.get_json() or {}
    node_id    = str(data.get("id", "")).strip()
    stream_url = str(data.get("stream_url", "")).strip()
    name = data.get("name", "")
    lat  = float(data.get("lat", 0.0) or 0.0)
    lng  = float(data.get("lng", 0.0) or 0.0)
    alarm_trigger_type = str(data.get("alarm_trigger_type", "PIR")).strip().upper()
    if alarm_trigger_type not in ["PIR", "DETECTION"]:
        alarm_trigger_type = "PIR"

    if not node_id or not stream_url:
        return jsonify({"error": "id and stream_url required"}), 400

    sys_obj = get_system()
    try:
        sys_obj.add_node(node_id, stream_url, name=name, lat=lat, lng=lng, alarm_trigger_type=alarm_trigger_type)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"status": "ok", "node_id": node_id})


@app.route("/api/nodes/<node_id>", methods=["PATCH"])
@require_role("COMMANDER")
def update_node(node_id):
    """
    Partially update a node. Accepts any combination of:
      name, stream_url, lat, lng, alarm_trigger_type
    Changes are applied live (stream_url restarts capture) and persisted to nodes.json.
    """
    data = request.get_json() or {}
    allowed = {"name", "stream_url", "lat", "lng", "alarm_trigger_type"}
    kwargs = {k: v for k, v in data.items() if k in allowed}
    if not kwargs:
        return jsonify({"error": "No valid fields provided. Allowed: name, stream_url, lat, lng"}), 400

    sys_obj = get_system()
    result = sys_obj.update_node(node_id, **kwargs)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result)


@app.route("/api/nodes/<node_id>", methods=["DELETE"])
@require_role("COMMANDER")
def remove_node(node_id):
    sys_obj = get_system()
    sys_obj.remove_node(node_id)
    return jsonify({"status": "ok", "message": f"Node {node_id} removed and clip folder archived"})



@app.route("/api/admin/simulate_threat/<node_id>", methods=["POST"])
@require_role("COMMANDER")
def admin_simulate_threat(node_id):
    sys_obj = get_system()
    sys_obj.simulate_threat(node_id)
    return jsonify({"status": "ok", "message": f"Threat simulated on {node_id}"})


@app.route("/api/admin/instant_alarm/<node_id>", methods=["POST"])
@require_role("COMMANDER")
def admin_instant_alarm(node_id):
    """Fire an instant alarm directly on a node (for testing / manual override).
    Works even if the node has no frame buffer."""
    sys_obj = get_system()
    if node_id not in sys_obj.nodes:
        return jsonify({"error": f"Node {node_id} not found"}), 404
    from detection_engine import Detection
    fake_det = Detection(x=100, y=100, w=200, h=300, confidence=0.99,
                         class_name="Person", source="manual", keypoints=None, metadata={})
    node = sys_obj.nodes[node_id]
    trigger_type = getattr(node, "alarm_trigger_type", "PIR")
    sys_obj.trigger_instant_alarm(node_id, [fake_det], from_inference=True)
    return jsonify({"status": "ok", "message": f"Instant alarm fired on {node_id} (type={trigger_type})"})


@app.route("/api/admin/set_background/<node_id>", methods=["POST"])
@require_role("COMMANDER")
def admin_set_background(node_id):
    sys_obj = get_system()
    sys_obj.set_permanent_background(node_id)
    return jsonify({"status": "ok", "message": f"Permanent background set for {node_id}"})


@app.route("/api/admin/clear_bg/<node_id>", methods=["POST"])
@require_role("COMMANDER")
def admin_clear_background(node_id):
    sys_obj = get_system()
    sys_obj.clear_permanent_background(node_id)
    return jsonify({"status": "ok", "message": f"Permanent background cleared for {node_id}"})


@app.route("/api/admin/telemetry", methods=["GET"])
@require_role("OPERATOR")
def admin_telemetry():
    sys_obj = get_system()
    return jsonify(sys_obj.get_telemetry())


@app.route("/api/admin/node_config/<node_id>", methods=["GET"])
@require_role("OPERATOR")
def admin_get_node_config(node_id):
    sys_obj = get_system()
    cfg = sys_obj.get_node_config(node_id)
    import dataclasses
    return jsonify(dataclasses.asdict(cfg))


@app.route("/api/admin/node_config/<node_id>", methods=["POST"])
@require_role("COMMANDER")
def admin_set_node_config(node_id):
    data = request.get_json()
    sys_obj = get_system()
    cfg = sys_obj.set_node_config(node_id, **data)
    import dataclasses
    return jsonify({"status": "ok", "config": dataclasses.asdict(cfg)})


@app.route("/api/admin/set_retention/<int:days>", methods=["POST"])
@require_role("COMMANDER")
def admin_set_retention(days):
    sys_obj = get_system()
    for nid in sys_obj.nodes.keys():
        sys_obj.set_node_config(nid, clip_retention_days=days)
    return jsonify({"status": "ok", "message": f"Clip retention set to {days} days globally"})


@app.route("/api/admin/acknowledge/<node_id>", methods=["POST"])
@require_role("OPERATOR")
def admin_acknowledge(node_id):
    """Operator acknowledges one threat on this node — decrements the active threat count."""
    sys_obj = get_system()
    sys_obj.acknowledge_node(node_id)
    return jsonify({"status": "ok", "message": f"Alarm acknowledged for {node_id}"})


@app.route("/api/admin/clear_clips", methods=["POST"])
@require_role("OPERATOR")
def admin_clear_clips():
    """Clear all saved clips from the server (calls archive logic)."""
    return clear_all_clips()


@app.route("/api/threats/active", methods=["GET"])
def get_active_threats():
    """Return all nodes that currently have unacknowledged threats, with lat/lng for map fit."""
    sys_obj = get_system()
    return jsonify(sys_obj.get_active_threats())




@app.route("/api/admin/set_viz_mode/<node_id>", methods=["POST"])
@require_role("OPERATOR")
def admin_set_viz_mode(node_id):
    """Set detection visualization mode: COMBINED | PRONG_A | PRONG_B."""
    data = request.get_json() or {}
    mode = data.get("mode", "COMBINED").upper()
    if mode not in {"COMBINED", "PRONG_A", "PRONG_B"}:
        return jsonify({"error": "mode must be COMBINED, PRONG_A, or PRONG_B"}), 400
    sys_obj = get_system()
    sys_obj.set_viz_mode(node_id, mode)
    return jsonify({"status": "ok", "mode": mode, "node_id": node_id})


@app.route("/api/admin/false_positive/<node_id>", methods=["POST"])
@require_role("OPERATOR")
def admin_false_positive(node_id):
    """
    Report a false positive on this node.
    Backend analyses which prong was responsible and auto-tunes sensitivity.
    """
    sys_obj = get_system()
    result = sys_obj.report_false_positive(node_id)
    return jsonify(result)






# ───────────────────────────────────────────────────────────
# DEBUG & DIAGNOSTICS ENDPOINTS
# ───────────────────────────────────────────────────────────

@app.route("/api/debug/<node_id>", methods=["GET"])
def debug_node(node_id):
    """
    Full live diagnostic snapshot for a single node.
    Returns: thread health, Prong A/B last-cycle metrics,
    inference timing, detection history, last exception, active config.
    """
    sys_obj = get_system()
    snap = sys_obj.get_debug_snapshot(node_id)
    if "error" in snap:
        return jsonify(snap), 404
    return jsonify(snap)


@app.route("/api/debug/exceptions", methods=["GET"])
def debug_exceptions():
    """
    Global exception ring buffer (last 100 exceptions across all nodes).
    Query params:
      ?node_id=HASH-1   filter by node
      ?limit=20         max results (default 50)
    """
    sys_obj = get_system()
    node_id = request.args.get("node_id")
    limit   = int(request.args.get("limit", 50))
    return jsonify(sys_obj.get_exception_log(node_id=node_id, limit=limit))


@app.route("/api/debug/pipeline", methods=["GET"])
def debug_pipeline_all():
    """
    Quick health summary for ALL nodes — one row per node.
    Useful for the admin panel overview without selecting a specific node.
    """
    sys_obj = get_system()
    result = []
    for nid in sys_obj.nodes:
        snap = sys_obj.get_debug_snapshot(nid)
        result.append({
            "node_id": nid,
            "name": snap.get("name"),
            "threads": snap.get("threads"),
            "pipeline": snap.get("pipeline"),
            "last_exception": snap.get("last_exception"),
            "viz_mode": snap.get("viz_mode"),
        })
    return jsonify(result)


# ───────────────────────────────────────────────────────────
# STARTUP
# ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  HASHTAG V2 - API SERVER v4")
    print("  SPACEBAR -> POST /api/analyze to trigger batch analysis")
    print("  Feeds: /video_feed/<node_id>")
    print("  Replay: /replay_feed/<job_id>/<node_id>")
    print("=" * 60)

    # Force system init before Flask starts
    sys_obj = get_system()
    time.sleep(2)  # Let nodes start their capture loops
    print(f"[SERVER] {len(sys_obj.nodes)} nodes online")

    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
