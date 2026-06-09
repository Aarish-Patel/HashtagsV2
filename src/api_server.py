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
from flask import Flask, Response, jsonify, request, send_from_directory, abort
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hashtag_v2_backend import get_system, AnalysisJob, CLIPS_DIR

app = Flask(__name__)
CORS(app)

# ───────────────────────────────────────────────────────────
# MJPEG frame generator helpers
# ───────────────────────────────────────────────────────────

STATIC_NO_SIGNAL = None

def _no_signal_frame(w=800, h=640):
    global STATIC_NO_SIGNAL
    if STATIC_NO_SIGNAL is None:
        img = 5 * (1 + int(time.time() * 2) % 2)  # subtle flicker
        frame = (5 + img) * __import__("numpy").ones((h, w, 3), dtype="uint8")
        cv2.putText(frame, "NO SIGNAL", (w//2 - 80, h//2),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (60, 60, 60), 2)
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        STATIC_NO_SIGNAL = buf.tobytes() if ok else b""
    return STATIC_NO_SIGNAL


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
# API ENDPOINTS
# ───────────────────────────────────────────────────────────

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
    """Serve a saved threat clip file."""
    safe_fn = os.path.basename(filename)
    if not os.path.exists(os.path.join(CLIPS_DIR, safe_fn)):
        abort(404)
    return send_from_directory(CLIPS_DIR, safe_fn, mimetype="video/mp4")


@app.route("/api/incidents/<path:filename>", methods=["DELETE"])
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
def clear_all_clips():
    """Delete all saved threat clips and reset counters."""
    sys_obj = get_system()
    count = 0
    for fname in os.listdir(CLIPS_DIR):
        fpath = os.path.join(CLIPS_DIR, fname)
        if os.path.isfile(fpath):
            try:
                os.remove(fpath)
                count += 1
            except Exception:
                pass
                
    # Reset node clip counters
    for node in sys_obj.nodes.values():
        node.clips_saved = 0
        
    return jsonify({"status": "ok", "deleted": count})


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


@app.route("/api/nodes/add", methods=["POST"])
def add_node():
    data = request.get_json()
    node_id = data.get("id", "").strip()
    stream_url = data.get("stream_url", "").strip()
    name = data.get("name", "")
    lat = float(data.get("lat", 0.0) or 0.0)
    lng = float(data.get("lng", 0.0) or 0.0)
    
    if not node_id or not stream_url:
        return jsonify({"error": "id and stream_url required"}), 400
        
    sys_obj = get_system()
    sys_obj.add_node(node_id, stream_url, name=name, lat=lat, lng=lng)
    return jsonify({"status": "ok", "node_id": node_id})


@app.route("/api/nodes/<node_id>", methods=["DELETE"])
def remove_node(node_id):
    sys_obj = get_system()
    sys_obj.remove_node(node_id)
    return jsonify({"status": "ok"})


@app.route("/api/admin/simulate_threat/<node_id>", methods=["POST"])
def admin_simulate_threat(node_id):
    sys_obj = get_system()
    sys_obj.simulate_threat(node_id)
    return jsonify({"status": "ok", "message": f"Threat simulated on {node_id}"})


@app.route("/api/admin/set_background/<node_id>", methods=["POST"])
def admin_set_background(node_id):
    sys_obj = get_system()
    sys_obj.set_permanent_background(node_id)
    return jsonify({"status": "ok", "message": f"Permanent background set for {node_id}"})


@app.route("/api/admin/clear_bg/<node_id>", methods=["POST"])
def admin_clear_background(node_id):
    sys_obj = get_system()
    sys_obj.clear_permanent_background(node_id)
    return jsonify({"status": "ok", "message": f"Permanent background cleared for {node_id}"})


@app.route("/api/admin/telemetry", methods=["GET"])
def admin_telemetry():
    sys_obj = get_system()
    return jsonify(sys_obj.get_telemetry())


@app.route("/api/admin/node_config/<node_id>", methods=["GET"])
def admin_get_node_config(node_id):
    sys_obj = get_system()
    cfg = sys_obj.get_node_config(node_id)
    import dataclasses
    return jsonify(dataclasses.asdict(cfg))


@app.route("/api/admin/node_config/<node_id>", methods=["POST"])
def admin_set_node_config(node_id):
    data = request.get_json()
    sys_obj = get_system()
    cfg = sys_obj.set_node_config(node_id, **data)
    import dataclasses
    return jsonify({"status": "ok", "config": dataclasses.asdict(cfg)})


@app.route("/api/admin/set_retention/<int:days>", methods=["POST"])
def admin_set_retention(days):
    sys_obj = get_system()
    for nid in sys_obj.nodes.keys():
        sys_obj.set_node_config(nid, clip_retention_days=days)
    return jsonify({"status": "ok", "message": f"Clip retention set to {days} days globally"})


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
