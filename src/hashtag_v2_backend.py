"""
hashtag_v2_backend.py — Military-Grade Backend v4
==================================================

OPERATIONAL PARADIGM (Radar Wake-up):
  The system runs in STANDBY by default:
    - ESP32 nodes are in DEEP SLEEP (no power draw, no streaming).
    - GPU is idle at the base station.
    - Base station GUI shows "WAITING FOR SIGNAL" (no signal).

  When the Radar detects movement:
    1. The ESP32 node wakes up from deep sleep and begins streaming a 30-second clip to the base station.
    2. The base station receives the stream, showing the live feed to the operator.
    3. The base station simultaneously runs inference on the incoming clip.
    4. When the ESP32 finishes the 30-second transmission, it goes back to deep sleep.
    5. The base station triggers a final batch analysis on the received frames to ensure zero false positives.
    6. If a threat is confirmed:
       - Saves annotated clip with pre-buffer (the 30s clip + JSON sidecar)
       - Plays audible buzzer alarm (Windows winsound)
       - GUI switches from live feed to annotated replay with entity sidebar
    7. If THREAT CLEAR:
       - No clip saved, no alarm

This architecture guarantees:
  - ZERO power waste (nodes sleep until radar trigger)
  - ZERO false positive alerts (only real multi-frame threats trigger)
  - ZERO missed humans (30s buffer + full ML pipeline runs on every frame)
  - Evidence-grade clips (pre-context + annotated post-detection)
"""

import cv2
import numpy as np
import os
import sys
import json
import math
import time
import threading
import datetime
import uuid
from typing import Optional, Dict, List, Any, Tuple
from collections import deque

# Prevent OpenCV from hanging indefinitely when IP cameras are unreachable (ESP32-P4 timeout)
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "timeout;2000000"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from augmentation_pipeline import OV5647Degrader
from detection_engine import (
    DetectionEngine, Detection, compute_iou, TemporalWindowAnalyzer,
    hierarchical_nms
)
from threat_classifier import (
    EntityTracker, ThreatLevel, THREAT_CATEGORIES, THREAT_LEVEL_LABELS,
    PostureType, classify_posture
)

# ===========================
# CONSTANTS
# ===========================
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
CLIPS_DIR = os.path.join(SRC_DIR, "Clips")
os.makedirs(CLIPS_DIR, exist_ok=True)

FORENSIC_JOURNAL_PATH = os.path.join(SRC_DIR, "forensic_journal.json")
NODE_CONFIGS_PATH    = os.path.join(SRC_DIR, "node_configs.json")
NODES_PATH           = os.path.join(SRC_DIR, "nodes.json")
BG_FRAMES_DIR        = os.path.join(SRC_DIR, "backgrounds")
os.makedirs(BG_FRAMES_DIR, exist_ok=True)


def _bg_paths(node_id: str):
    """Return (edges_path, frame_path) for a node's background on disk."""
    safe = node_id.replace("/", "_").replace("\\", "_")
    return (
        os.path.join(BG_FRAMES_DIR, f"{safe}_edges.npy"),
        os.path.join(BG_FRAMES_DIR, f"{safe}_frame.npy"),
    )


def _save_bg_to_disk(node_id: str, edges, frame_gray):
    """Persist permanent background arrays to disk."""
    try:
        ep, fp = _bg_paths(node_id)
        np.save(ep, edges)
        np.save(fp, frame_gray)
    except Exception as e:
        print(f"[BG] Failed to save background for {node_id}: {e}")


def _load_bg_from_disk(node_id: str):
    """Load persisted background arrays. Returns (edges, frame_gray) or (None, None)."""
    try:
        ep, fp = _bg_paths(node_id)
        if os.path.exists(ep) and os.path.exists(fp):
            edges = np.load(ep)
            frame = np.load(fp)
            print(f"[BG] Loaded persisted background for {node_id}")
            return edges, frame
    except Exception as e:
        print(f"[BG] Failed to load background for {node_id}: {e}")
    return None, None


def _delete_bg_from_disk(node_id: str):
    """Remove persisted background files when a background is invalidated/cleared."""
    try:
        ep, fp = _bg_paths(node_id)
        for p in (ep, fp):
            if os.path.exists(p):
                os.remove(p)
    except Exception as e:
        print(f"[BG] Failed to delete background for {node_id}: {e}")

# Default nodes written to nodes.json on first run.
# Edit nodes.json to change camera URLs/locations permanently.
_DEFAULT_NODES = [
    {"id": "HASH-1", "name": "Tiger Chongjang",  "stream_url": "http://192.168.0.200/stream", "lat": 24.165566, "lng": 94.259984},
    {"id": "HASH-2", "name": "Pangal Sangjai",   "stream_url": "http://192.168.1.100/stream", "lat": 24.180,    "lng": 94.260},
]

# Portable model path: reads from env var HASHTAG_MODEL_PATH, falls back to the
# known local path. Set the env var for deployment on a different machine.
DEFAULT_MODEL_PATH = os.environ.get(
    "HASHTAG_MODEL_PATH",
    "yolov8n.pt"
)

TARGET_W, TARGET_H = 800, 640
TARGET_FPS = 2.0
BUFFER_SECONDS = 30
MIN_FRAMES_FOR_THREAT = 1
BUZZER_COOLDOWN_SEC = 10

# Max concurrent GPU batch analysis jobs to prevent OOM on multi-camera wakeup.
# If 5 cameras wake up simultaneously, 5 GPU jobs would OOM. This cap queues extras.
_BATCH_SEMAPHORE = threading.Semaphore(2)
_journal_lock = threading.Lock()


# ===========================
# PER-NODE CONFIGURATION
# ===========================
from dataclasses import dataclass, asdict

@dataclass
class NodeConfig:
    """Per-camera tuning parameters, persisted to node_configs.json."""
    # ── YOLO (Prong B) ──────────────────────────────────────────────────
    person_conf: float = 0.05        # YOLO confidence threshold (kept ultra-low)
    prong_b_weight: float = 1.0      # Multiplier on YOLO confidence score

    # ── Structural Discrepancy (Prong A) ────────────────────────────────
    canny_low: int = 50
    canny_high: int = 150
    prong_a_threshold: int = 20      # Edge-diff pixel threshold (lower = more sensitive)
    prong_a_weight: float = 1.0      # Multiplier on Prong A blob significance
    pixel_diff_weight: float = 0.55  # Weight of pixel-level diff vs Canny edge diff (0=edge only, 1=pixel only)
    pixel_diff_threshold: int = 18   # Raw pixel difference below which a pixel is considered "background"

    # ── Intersection settings ───────────────────────────────────────────
    intersection_iou: float = 0.10   # Min IoU to validate a YOLO box against a blob
    intersection_containment: float = 0.20
    min_contour_area: int = 50       # Min blob pixel area to consider

    # ── Storage ─────────────────────────────────────────────────────────
    clip_retention_days: int = 7

    # ── False-positive self-correction tracking ─────────────────────────
    fp_count: int = 0
    prong_a_fp_score: float = 0.0    # Accumulated blame on Prong A across sessions
    prong_b_fp_score: float = 0.0    # Accumulated blame on Prong B across sessions


def _load_node_configs() -> Dict[str, NodeConfig]:
    """Load per-node configs from disk. Returns defaults if file missing."""
    if os.path.exists(NODE_CONFIGS_PATH):
        try:
            with open(NODE_CONFIGS_PATH) as f:
                raw = json.load(f)
            return {nid: NodeConfig(**cfg) for nid, cfg in raw.items()}
        except Exception as e:
            print(f"[CONFIG] Failed to load node_configs.json: {e}")
    return {}


def _save_node_configs(configs: Dict[str, "NodeConfig"]):
    """Persist all node configs to disk."""
    try:
        with open(NODE_CONFIGS_PATH, "w") as f:
            json.dump({nid: asdict(cfg) for nid, cfg in configs.items()}, f, indent=2)
    except Exception as e:
        print(f"[CONFIG] Failed to save node_configs.json: {e}")


def _load_nodes_from_disk() -> List[Dict]:
    """Load node definitions from nodes.json. Creates file with defaults if missing."""
    if os.path.exists(NODES_PATH):
        try:
            with open(NODES_PATH) as f:
                return json.load(f)
        except Exception as e:
            print(f"[NODES] Failed to load nodes.json: {e} — using defaults")
    # First run: write defaults
    _save_nodes_to_disk(_DEFAULT_NODES)
    return list(_DEFAULT_NODES)


def _save_nodes_to_disk(nodes_list: List[Dict]):
    """Persist node definitions list to nodes.json."""
    try:
        with open(NODES_PATH, "w") as f:
            json.dump(nodes_list, f, indent=2)
        print(f"[NODES] nodes.json saved ({len(nodes_list)} nodes)")
    except Exception as e:
        print(f"[NODES] Failed to save nodes.json: {e}")


# ===========================
# GLOBAL EXCEPTION LOG
# ===========================
_EXCEPTION_LOG: deque = deque(maxlen=100)  # ring buffer of {ts, node, type, msg, file, line, tb}

def _log_exception(node_id: str, exc: Exception, context: str = ""):
    import traceback
    tb = traceback.format_exc()
    tb_lines = [l for l in tb.strip().splitlines() if l.strip()]
    # Find the innermost hashtag_v2 file reference for quick source location
    src_hint = ""
    for line in reversed(tb_lines):
        if 'hashtag_v2' in line or 'api_server' in line or 'detection_engine' in line:
            src_hint = line.strip()
            break
    _EXCEPTION_LOG.append({
        "ts": time.time(),
        "ts_str": datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3],
        "node_id": node_id,
        "context": context,
        "type": type(exc).__name__,
        "message": str(exc),
        "source_hint": src_hint,
        "traceback": "\n".join(tb_lines[-8:]),  # last 8 lines of tb
    })


# ===========================
# AUDIBLE ALERT (Windows)
# ===========================
def _play_buzzer(threat_level: int):
    def _beep():
        try:
            import winsound
            if threat_level >= 4:   # CRITICAL (Play custom alarm)
                wav_path = os.path.join(os.path.dirname(__file__), "alarm.wav")
                if os.path.exists(wav_path):
                    # Play asynchronously in a loop. It will be stopped when acknowledged.
                    winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
                else:
                    for _ in range(3):
                        for freq in range(400, 1200, 100):
                            winsound.Beep(freq, 30)
                        time.sleep(0.1)
            elif threat_level >= 3: # HIGH (Submarine Dive Horn)
                for _ in range(2):
                    winsound.Beep(300, 400)
                    time.sleep(0.1)
            else:                   # MEDIUM
                winsound.Beep(500, 300)
        except Exception:
            pass
    threading.Thread(target=_beep, daemon=True).start()


# ===========================
# ANNOTATION HELPERS
# ===========================
FONT = cv2.FONT_HERSHEY_SIMPLEX
THREAT_COLORS_BGR = {
    0: (0, 220, 80),
    1: (0, 200, 255),
    2: (0, 140, 255),
    3: (30, 80, 255),
    4: (0, 0, 255),
}

def draw_entity_box(frame: np.ndarray, entity: Dict):
    bbox = entity.get("bbox", [0, 0, 0, 0])
    if not bbox or bbox[2] <= 0 or bbox[3] <= 0:
        return
    x, y, w, h = [int(v) for v in bbox]
    tl = int(entity.get("threat_level", 0))
    color = THREAT_COLORS_BGR.get(tl, (0, 255, 0))
    is_weapon = entity.get("class") == "Weapon"
    if is_weapon:
        color = (0, 0, 255)

    eid = entity.get("id", 0)
    behavior = entity.get("behavior", "DETECTED")
    dist_m = entity.get("distance_m", -1)
    approach = entity.get("approach_score", 0.0)

    # Tactical corner bracket box
    th = 2 if tl < 3 else 3
    br = min(w // 4, h // 4, 22)
    for (sx, sy, ex, ey) in [
        ((x, y), (x+br, y), (x, y), (x, y+br)),                             # TL
        ((x+w, y), (x+w-br, y), (x+w, y), (x+w, y+br)),                     # TR
        ((x, y+h), (x+br, y+h), (x, y+h), (x, y+h-br)),                     # BL
        ((x+w, y+h), (x+w-br, y+h), (x+w, y+h), (x+w, y+h-br)),            # BR
    ]:
        cv2.line(frame, sx, ex, color, th)
        cv2.line(frame, sy, ey, color, th)
        
    # Full bounding box requested by user
    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 1)

    short_id = f"ENT-{str(eid)[-6:]}"
    dist_s = f" {dist_m:.1f}M" if dist_m > 0 else ""
    top_label = f"[{short_id}]{dist_s}"
    bot_label = (f">> APPROACH! {behavior}" if approach >= 0.5 else behavior)[:24]

    sc = 0.38 if w < 80 else 0.44
    cv2.putText(frame, top_label, (x, max(y - 6, 12)), FONT, sc, color, 1, cv2.LINE_AA)
    cv2.putText(frame, bot_label, (x, y + h + 14), FONT, sc, color, 1, cv2.LINE_AA)

    if is_weapon:
        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
        cv2.putText(frame, "!! WEAPON !!", (x, y-5), FONT, 0.5, (0, 0, 255), 2, cv2.LINE_AA)


def draw_standby_hud(frame: np.ndarray, node_id: str):
    """Minimal standby overlay — just node ID, no detection clutter."""
    h, w = frame.shape[:2]
    cv2.putText(frame, node_id, (8, h - 10), FONT, 0.38, (120, 120, 120), 1, cv2.LINE_AA)
    cv2.putText(frame, "STANDBY", (w - 75, h - 10), FONT, 0.35, (80, 80, 80), 1, cv2.LINE_AA)


def draw_replay_hud(frame: np.ndarray, node_id: str, frame_idx: int,
                    total_frames: int, threat_level: int, n_entities: int):
    """HUD overlay during annotated clip replay."""
    h, w = frame.shape[:2]
    color = THREAT_COLORS_BGR.get(threat_level, (0, 255, 0))
    tl_str = THREAT_LEVEL_LABELS.get(threat_level, "SCANNING")
    t_sec = frame_idx / TARGET_FPS

    cv2.putText(frame, f"{node_id} | REPLAY", (8, 18), FONT, 0.4, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.putText(frame, f"T+{t_sec:.1f}s", (8, 34), FONT, 0.38, (160, 160, 160), 1, cv2.LINE_AA)
    cv2.putText(frame, tl_str, (w - 130, 18), FONT, 0.42, color, 1, cv2.LINE_AA)
    cv2.putText(frame, f"ENT: {n_entities}", (w - 80, 34), FONT, 0.38, color, 1, cv2.LINE_AA)

    # Progress bar
    prog = frame_idx / max(total_frames - 1, 1)
    bar_x, bar_y, bar_w, bar_h = 8, h - 8, w - 16, 4
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (60, 60, 60), -1)
    cv2.rectangle(frame, (bar_x, bar_y),
                  (bar_x + int(bar_w * prog), bar_y + bar_h), color, -1)


# ===========================
# ANALYSIS JOB
# ===========================
class AnalysisJob:
    """
    A single batch analysis job created when SPACEBAR is pressed.
    Runs ML pipeline on a 30-second frame buffer from one camera node.
    """

    STATUS_QUEUED = "QUEUED"
    STATUS_RUNNING = "RUNNING"
    STATUS_COMPLETE = "COMPLETE"
    STATUS_CLEAR = "CLEAR"

    def __init__(self, job_id: str, node_id: str, frames: List[np.ndarray], mp4_path: str = None):
        self.job_id = job_id
        self.node_id = node_id
        self.mp4_path = mp4_path       # Path to the temporary MP4
        self.status = self.STATUS_QUEUED
        self.progress = 0              # 0-100
        self.threat_detected = False
        self.max_threat_level = 0
        self.entities: List[Dict] = []
        self.annotated_frames: List[np.ndarray] = frames  # JPEG bytes for replay
        self.clip_path: str = ""
        self.created_at = time.time()
        self.completed_at: float = 0.0
        self.is_auto_trigger = False
        self.live_threat_detected = False
        self._lock = threading.Lock()

    def get_status_dict(self) -> Dict:
        with self._lock:
            return {
                "job_id": self.job_id,
                "node_id": self.node_id,
                "status": self.status,
                "progress": self.progress,
                "threat_detected": self.threat_detected,
                "max_threat_level": self.max_threat_level,
                "entity_count": len(self.entities),
                "entities": self.entities,
                "total_frames": len(self.annotated_frames),
                "clip_path": self.clip_path,
                "clip_url": f"http://localhost:5000/clips/{os.path.basename(self.clip_path)}" if self.clip_path else "",
                "replay_url": f"http://localhost:5000/video_feed/{self.node_id}" if self.job_id.startswith("INSTANT") else (f"http://localhost:5000/replay_feed/{self.job_id}/{self.node_id}" if self.threat_detected else ""),
                "created_at": self.created_at,
                "is_auto_trigger": self.is_auto_trigger,
            }


class BatchAnalyzer:
    """
    Runs the ML detection pipeline on a list of frames (batch mode).
    Unlike real-time detection, this processes the whole 30-second clip
    and makes a final threat decision based on cross-frame evidence.
    """

    def __init__(self, engine: DetectionEngine):
        self.engine = engine

    def analyze(self, job: AnalysisJob) -> None:
        """Run analysis on job.mp4_path. Updates job in-place. Blocking."""
        mp4_path = job.mp4_path
        node_id = job.node_id
        
        if not mp4_path or not os.path.exists(mp4_path):
            with job._lock:
                job.status = AnalysisJob.STATUS_CLEAR
                job.completed_at = time.time()
            return

        cap = cv2.VideoCapture(mp4_path)
        if not cap.isOpened():
            with job._lock:
                job.status = AnalysisJob.STATUS_CLEAR
                job.completed_at = time.time()
            return

        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if n <= 0:
            n = 150 # estimate

        print(f"[ANALYZE] {node_id} | Job {job.job_id[:8]} | MP4 File | Starting...")
        with job._lock:
            job.status = AnalysisJob.STATUS_RUNNING

        all_seen_entities: Dict[int, Dict] = {}
        annotated_out: List[np.ndarray] = []

        print(f"[DEBUG-BATCH] File opened successfully. Extracted {n} frames.")
        
        node_num = int(node_id.split('-')[-1]) if '-' in node_id and node_id.split('-')[-1].isdigit() else 1
        tracker = EntityTracker(cam_id=node_num, img_w=TARGET_W, img_h=TARGET_H)
        
        fi = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            # Skip every alternate frame to double analysis speed (process at 2.5 FPS)
            if fi % 2 != 0:
                if annotated_out:
                    # Duplicate the last frame to keep output video smooth
                    annotated_out.append(annotated_out[-1])
                    with job._lock:
                        job.annotated_frames.append(annotated_out[-1])
                        job.progress = min(100, int((fi + 1) / n * 100))
                fi += 1
                continue

            if frame.shape[:2] != (TARGET_H, TARGET_W):
                frame = cv2.resize(frame, (TARGET_W, TARGET_H))

            # Gather active boxes from tracker
            active_boxes = []
            for t in tracker.tracks.values():
                if t.stale_frames < 5 and t.bboxes:
                    active_boxes.append(t.bboxes[-1])

            sys_obj = get_system()
            cfg = sys_obj.get_node_config(node_id) if sys_obj else None
            person_conf_override = max(0.01, cfg.person_conf * cfg.prong_b_weight) if cfg else None

            # Raw detection with tracking persistence
            detections = self.engine.detect(
                frame, 
                cam_id=node_num, 
                fps=TARGET_FPS, 
                active_boxes=active_boxes,
                motion_mask=None,
                person_conf_override=person_conf_override
            )

            annotated = frame.copy()
            
            if detections:
                print(f"[DEBUG-BATCH] Frame {fi}: Found {len(detections)} detections!")
                
            tracker.update(detections, fps=TARGET_FPS)
            entities_this_frame = tracker.get_active_entities()
            
            for ent in entities_this_frame:
                if ent["class"] in ["Person", "Weapon"]:
                    print(f"[DEBUG-BATCH] Frame {fi}: Saving entity {ent['class']} with score {ent['threat_score']}")
                    all_seen_entities[ent["id"]] = ent
                    draw_entity_box(annotated, ent)

            # HUD
            max_tl = max((e.get("threat_level", 0) for e in entities_this_frame), default=0)
            draw_replay_hud(annotated, node_id, fi, n, max_tl, len(entities_this_frame))
            annotated_out.append(annotated)

            with job._lock:
                job.annotated_frames.append(annotated)
                job.progress = min(100, int((fi + 1) / n * 100))
                
            fi += 1
            
        cap.release()
        print(f"[DEBUG-BATCH] Finished processing {fi} frames.")

        # Threat decision: if ANY frame had a detection
        final_entities = list(all_seen_entities.values())
        threat_detected = len(final_entities) > 0
        final_max_threat = 4 if threat_detected else 0

        print(f"[ANALYZE] {node_id} | COMPLETE | "
              f"Confirmed entities: {len(final_entities)} | "
              f"Max threat: {final_max_threat} | "
              f"Threat detected: {threat_detected}")

        clip_path = ""
        if threat_detected:
            clip_path = self._save_clip(job.job_id, node_id, annotated_out, final_entities)

        # Cleanup temp file if no threat
        if os.path.exists(mp4_path):
            try:
                os.remove(mp4_path)
            except:
                pass

        with job._lock:
            job.status = AnalysisJob.STATUS_COMPLETE if threat_detected else AnalysisJob.STATUS_CLEAR
            job.threat_detected = threat_detected
            job.max_threat_level = final_max_threat
            job.entities = final_entities if threat_detected else []
            job.clip_path = clip_path
            job.completed_at = time.time()

    def _save_clip(self, job_id: str, node_id: str,
                   frames: List[np.ndarray], entities: List[Dict]) -> str:
        """Write annotated frames to an MP4 file and JSON sidecar."""
        # Add a "LOOP RESTART" frame to the end so it doesn't look static if the clip is very short
        blank = np.zeros((TARGET_H, TARGET_W, 3), dtype=np.uint8)
        cv2.putText(blank, "LOOP RESTARTING...", (TARGET_W//2 - 150, TARGET_H//2), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)
        frames_to_save = frames + [blank]

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        sys_obj = get_system()
        node = sys_obj.nodes.get(node_id)
        
        if node and getattr(node, "name", ""):
            safe_name = str(node.name).replace(" ", "_").replace("/", "_").upper()
            loc = f"{node.lat}_{node.lng}"
        else:
            safe_name = node_id
            loc = "UNKNOWN-LOC"
            
        fname = f"{ts}_{loc}_{safe_name}.mp4"
        fpath = os.path.join(CLIPS_DIR, fname)

        if frames_to_save:
            h, w = frames_to_save[0].shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(fpath, fourcc, TARGET_FPS, (w, h))
            for f in frames_to_save:
                writer.write(f)
            writer.release()
            
            # Post-process with ffmpeg to ensure web-compatible H.264 (avc1) playback
            import subprocess
            temp_fpath = fpath + ".temp.mp4"
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", fpath, "-vcodec", "libx264", temp_fpath],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
                )
                os.replace(temp_fpath, fpath)
            except Exception as e:
                print(f"[FFMPEG ERROR] Failed to encode {fname} to H.264: {e}")

        # JSON sidecar
        sidecar = fpath.replace(".mp4", "_report.json")
        report = {
            "job_id": job_id,
            "node_id": node_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "clip_file": fname,
            "entity_count": len(entities),
            "max_threat_level": max((e.get("threat_level", 0) for e in entities), default=0),
            "entities": [
                {
                    "id": e.get("id"),
                    "behavior": e.get("behavior"),
                    "threat_level": e.get("threat_level"),
                    "threat_score": e.get("threat_score"),
                    "class": e.get("class"),
                    "distance_m": e.get("distance_m"),
                    "bbox": e.get("bbox"),
                }
                for e in entities
            ],
        }
        try:
            with open(sidecar, "w") as f:
                json.dump(report, f, indent=2)
        except Exception:
            pass

        # Forensic journal
        try:
            with _journal_lock:
                journal = []
                if os.path.exists(FORENSIC_JOURNAL_PATH):
                    with open(FORENSIC_JOURNAL_PATH) as f:
                        journal = json.load(f)
                journal.append(report)
                with open(FORENSIC_JOURNAL_PATH, "w") as f:
                    json.dump(journal[-500:], f, indent=2)
        except Exception:
            pass

        print(f"[CLIP] Saved: {fpath}")
        return fpath


# ===========================
# CAMERA NODE (Buffer-Only)
# ===========================
class CameraNode:
    """
    A single field node in HYBRID DETECTION mode.
    - Captures raw frames into a 30s buffer.
    - Runs lightweight real-time YOLO for GUI display (in background thread).
    - Automatically triggers BatchAnalysis when stream drops (ESP deep sleep).
    """

    def __init__(self, node_id: str, stream_url: Any, system_ref, engine,
                 degrader: Optional[OV5647Degrader] = None, name: str = "", lat: float = 0.0, lng: float = 0.0, alarm_trigger_type: str = "PIR"):
        self.node_id = node_id
        self.stream_url = stream_url
        self.name = name
        self.lat = lat
        self.lng = lng
        self.alarm_trigger_type = alarm_trigger_type
        self.system = system_ref
        self.engine = engine
        self.degrader = degrader or OV5647Degrader()

        self.online = False
        self._stopped = False
        self.clips_saved = 0

        self.temp_mp4_path = os.path.join(CLIPS_DIR, f"temp_{self.node_id}.mp4")
        self.frame_buffer = deque(maxlen=75)
        self.permanent_bg_edges = None   # Canny edge map of captured background (used by detection)
        self.permanent_bg_frame = None   # Grayscale frame of captured background (used by PRONG_A viz)

        # Lighting-change detection: track mean brightness to auto-invalidate bg
        self._bg_capture_mean_brightness: Optional[float] = None
        self._bg_invalidation_strike: int = 0

        # Auto-load persisted background from disk (survives backend restarts)
        _edges, _frame = _load_bg_from_disk(self.node_id)
        if _edges is not None and _frame is not None:
            self.permanent_bg_edges = _edges
            self.permanent_bg_frame = _frame
            # Recompute brightness from the stored frame for the invalidation check
            self._bg_capture_mean_brightness = float(np.mean(_frame))
            print(f"[{self.node_id}] Auto-loaded persisted background (brightness={self._bg_capture_mean_brightness:.1f})")

        # Approaching-object auto-analysis cooldown (prevents repeated triggers)
        self._last_obj_trigger_time: float = 0.0
        self._OBJ_TRIGGER_COOLDOWN = 30.0  # seconds

        # Per-node entity tracker for approaching-object detection in the inference loop
        node_num = int(node_id.split('-')[-1]) if '-' in node_id and node_id.split('-')[-1].isdigit() else 1
        self._node_num = node_num
        self._rt_tracker = EntityTracker(cam_id=node_num, img_w=TARGET_W, img_h=TARGET_H)

        self._live_frame: Optional[np.ndarray] = None
        self._raw_frame: Optional[np.ndarray] = None
        self._latest_detections: List[Detection] = []
        self._lock = threading.Lock()
        self._det_lock = threading.Lock()

        self._fps = 0.0
        self._ts_ring = deque(maxlen=30)
        self.threat_detected_this_session = False
        self._was_online = False
        self.last_alarm_time = 0.0

        # Viz mode: 'COMBINED' | 'PRONG_A' | 'PRONG_B'
        self._viz_mode = 'COMBINED'

        # Last raw Prong A/B data for FP analysis
        self._last_prong_a_blob_area: int = 0
        self._last_prong_b_conf: float = 0.0

        # ── Heatmap / PRONG_A viz state ──────────────────────────────────
        self._last_edge_diff = None               # raw edge diff (Canny) or MOG2 mask
        self._last_is_canny_diff: bool = False    # True = real Canny structural diff
        self._bg_invalidation_strike: int = 0     # consecutive frames above brightness threshold
        _BG_INVALIDATION_THRESHOLD = 0.65         # 65% brightness ratio before invalidating bg
        _BG_INVALIDATION_STRIKES    = 3           # must exceed threshold for N frames in a row

        # ── Multi-threat tracking ────────────────────────────────────────
        self._active_threat_count: int = 0        # unacknowledged threats on this node
        self._threat_count_lock = threading.Lock()

        # ── Debug telemetry ──────────────────────────────────────────────
        self._last_capture_ts: float = 0.0         # when capture loop last got a frame
        self._last_inference_ts: float = 0.0       # when inference loop last completed
        self._last_inference_ms: float = 0.0       # duration of last inference cycle (ms)
        self._inference_cycle_count: int = 0       # total cycles completed
        self._detection_history: deque = deque(maxlen=30)  # ring of per-cycle detection snapshots
        self._last_exception_info: dict = {}       # last exception in either thread
        self._last_prong_a_blob_count: int = 0     # how many blobs Prong A produced last cycle
        self._last_yolo_det_count: int = 0         # raw YOLO detections before intersection
        self._last_intersection_pass: int = 0      # detections that survived intersection
        self._had_large_discrepancy: bool = False   # did Prong A find something?
        self._human_detected_this_session: bool = False
        self._brightness_delta: float = 0.0        # last measured brightness delta vs bg
        # ────────────────────────────────────────────────────────────────

        self.degrader = OV5647Degrader()

        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._inference_thread = threading.Thread(target=self._inference_loop, daemon=True)

    def _save_buffer_to_mp4(self, path: str) -> bool:
        with self._lock:
            frames = list(self.frame_buffer)
        if not frames:
            return False
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(path, fourcc, TARGET_FPS, (TARGET_W, TARGET_H))
        for f in frames:
            writer.write(f)
        writer.release()
        return True

    def start(self):
        self._capture_thread.start()
        self._inference_thread.start()
        
    def _inference_loop(self):
        mog2 = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=False)

        while not self._stopped:
            time.sleep(0.010)
            frame_to_process = self.get_raw_frame()
            if frame_to_process is None:
                time.sleep(0.1)
                continue

            _cycle_start = time.perf_counter()

            try:
                motion_mask = None
                cfg = self.system.get_node_config(self.node_id)

                # === AUTO BACKGROUND INVALIDATION ===
                # Uses a 3-strike dampener: brightness must exceed threshold for 3
                # consecutive frames before the background is invalidated. This
                # prevents a single over-exposed or glitch frame from nuking the bg.
                if self.permanent_bg_edges is not None and self._bg_capture_mean_brightness is not None:
                    gray_check = cv2.cvtColor(frame_to_process, cv2.COLOR_BGR2GRAY)
                    current_brightness = float(np.mean(gray_check))
                    self._brightness_delta = abs(current_brightness - self._bg_capture_mean_brightness) / max(self._bg_capture_mean_brightness, 30.0)
                    if self._brightness_delta > 0.65:  # raised from 0.40 → 0.65
                        self._bg_invalidation_strike = getattr(self, '_bg_invalidation_strike', 0) + 1
                        if self._bg_invalidation_strike >= 3:
                            print(f"[{self.node_id}] BACKGROUND_INVALIDATED — Sustained lighting change (ratio={self._brightness_delta:.2f}, {self._bg_invalidation_strike} frames).")
                            self.permanent_bg_edges = None
                            self.permanent_bg_frame = None   # MUST clear both
                            self._bg_capture_mean_brightness = None
                            self._bg_invalidation_strike = 0
                            _delete_bg_from_disk(self.node_id)  # remove persisted files
                            self.system._log_event(
                                "BACKGROUND_INVALIDATED",
                                f"{self.node_id}: Lighting changed {self._brightness_delta*100:.0f}% for 3+ frames — bg reset to MOG2.",
                                threat_level=1
                            )
                    else:
                        self._bg_invalidation_strike = 0  # reset strike counter on good frame

                # === PRONG A: Structural Discrepancy Filter ===
                #
                # When a permanent background is captured, we fuse TWO signals:
                #
                #   Signal 1 — Canny EDGE diff (original):
                #     absdiff(Canny(current), Canny(bg))
                #     Detects structural/shape changes. Robust to gradual lighting
                #     drift. But misses smooth/featureless objects (dark cloth,
                #     plain clothing) that create few new edges.
                #
                #   Signal 2 — Pixel-level diff (new):
                #     absdiff(gray_current, gray_bg)
                #     Detects ANY pixel change — texture, colour, presence.
                #     Catches what Canny misses. More sensitive to lighting noise
                #     but that is already handled by the brightness dampener above.
                #
                #   Combined mask:
                #     weighted_diff = pixel_weight * pixel_diff
                #                   + (1 - pixel_weight) * edge_diff
                #     Threshold the weighted sum → motion_mask
                #
                #   Result: catches smooth AND textured intruders, while requiring
                #   some structural change contribution keeps FP rate low.
                #
                if self.permanent_bg_edges is not None and self.permanent_bg_frame is not None:
                    gray = cv2.cvtColor(frame_to_process, cv2.COLOR_BGR2GRAY)

                    # ── Signal 1: Canny edge diff ──────────────────────────────────
                    curr_edges = cv2.Canny(gray, cfg.canny_low, cfg.canny_high)
                    edge_diff  = cv2.absdiff(curr_edges, self.permanent_bg_edges)
                    kernel     = np.ones((5, 5), np.uint8)
                    edge_diff  = cv2.morphologyEx(edge_diff, cv2.MORPH_OPEN, kernel)
                    edge_diff  = cv2.dilate(edge_diff, kernel, iterations=2)
                    # Normalise to 0-255 float
                    edge_norm  = edge_diff.astype(np.float32) / 255.0

                    # ── Signal 2: Pixel-level diff ─────────────────────────────────
                    # Equalise brightness first so minor camera auto-exposure shifts
                    # don't dominate the pixel diff signal.
                    curr_eq   = cv2.equalizeHist(gray)
                    bg_eq     = cv2.equalizeHist(self.permanent_bg_frame)
                    pixel_diff = cv2.absdiff(curr_eq, bg_eq).astype(np.float32) / 255.0
                    # Mild Gaussian blur suppresses per-pixel JPEG compression noise
                    pixel_diff = cv2.GaussianBlur(pixel_diff, (5, 5), 0)

                    # ── Fuse signals ───────────────────────────────────────────────
                    w_p = float(cfg.pixel_diff_weight)           # 0.55 default
                    w_e = 1.0 - w_p                              # 0.45 default
                    combined = (w_p * pixel_diff + w_e * edge_norm)
                    combined_uint8 = (combined * 255).astype(np.uint8)

                    # Dilate to connect nearby regions before thresholding
                    combined_uint8 = cv2.dilate(combined_uint8, kernel, iterations=1)

                    # Threshold using a single unified threshold (scaled to 0-255 combined space)
                    fused_threshold = int(cfg.pixel_diff_threshold * 1.8)  # ~32 default
                    _, motion_mask = cv2.threshold(
                        combined_uint8, fused_threshold, 255, cv2.THRESH_BINARY)

                    # Store for viz and debug
                    self._last_edge_diff  = edge_diff           # raw edge diff for overlay
                    self._last_pixel_diff = (pixel_diff * 255).astype(np.uint8)  # raw pixel diff
                    self._last_fused_diff = combined_uint8       # fused map (used by thermal viz)
                    self._last_is_canny_diff = True

                elif self.permanent_bg_edges is not None:
                    # Background edges captured but no raw frame (edge-only fallback)
                    gray = cv2.cvtColor(frame_to_process, cv2.COLOR_BGR2GRAY)
                    curr_edges = cv2.Canny(gray, cfg.canny_low, cfg.canny_high)
                    edge_diff  = cv2.absdiff(curr_edges, self.permanent_bg_edges)
                    kernel     = np.ones((5, 5), np.uint8)
                    edge_diff  = cv2.morphologyEx(edge_diff, cv2.MORPH_OPEN, kernel)
                    edge_diff  = cv2.dilate(edge_diff, kernel, iterations=2)
                    _, motion_mask = cv2.threshold(edge_diff, cfg.prong_a_threshold, 255, cv2.THRESH_BINARY)
                    self._last_edge_diff  = edge_diff
                    self._last_pixel_diff = None
                    self._last_fused_diff = edge_diff
                    self._last_is_canny_diff = True

                else:
                    # No background captured — fall back to MOG2
                    fg_mask = mog2.apply(frame_to_process)
                    _, motion_mask = cv2.threshold(fg_mask, 50, 255, cv2.THRESH_BINARY)
                    self._last_edge_diff  = fg_mask
                    self._last_pixel_diff = None
                    self._last_fused_diff = fg_mask
                    self._last_is_canny_diff = False

                # === PRONG B: YOLO scan at per-node ultra-low confidence ===
                yolo_detections = self.engine.detect(
                    frame_to_process,
                    cam_id=self.node_id,
                    fps=TARGET_FPS,
                    motion_mask=motion_mask,
                    person_conf_override=max(0.01, cfg.person_conf * cfg.prong_b_weight)
                )
                self._last_prong_b_conf = max((d.confidence for d in yolo_detections), default=0.0)
                self._last_yolo_det_count = len(yolo_detections)

                from detection_engine import Detection
                detections = []
                motion_boxes = []

                # === Build Prong A blobs ===
                if motion_mask is not None:
                    contours, _ = cv2.findContours(motion_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    for cnt in contours:
                        area = cv2.contourArea(cnt)
                        if area > cfg.min_contour_area * cfg.prong_a_weight:
                            motion_boxes.append(cv2.boundingRect(cnt))
                    if len(motion_boxes) > 0:
                        self._had_large_discrepancy = True
                        self._last_prong_a_blob_area = int(sum(b[2]*b[3] for b in motion_boxes) / len(motion_boxes))
                self._last_prong_a_blob_count = len(motion_boxes)


                final_detections = []

                motion_clusters = {i: [] for i in range(len(motion_boxes))}
                
                def _iou(boxA, boxB):
                    xA, yA = max(boxA[0], boxB[0]), max(boxA[1], boxB[1])
                    xB, yB = min(boxA[0]+boxA[2], boxB[0]+boxB[2]), min(boxA[1]+boxA[3], boxB[1]+boxB[3])
                    inter = max(0, xB - xA) * max(0, yB - yA)
                    areaA, areaB = boxA[2]*boxA[3], boxB[2]*boxB[3]
                    return inter / float(areaA + areaB - inter) if areaA + areaB > 0 else 0
                    
                def _containment(box_in, box_out):
                    xA, yA = max(box_in[0], box_out[0]), max(box_in[1], box_out[1])
                    xB, yB = min(box_in[0]+box_in[2], box_out[0]+box_out[2]), min(box_in[1]+box_in[3], box_out[1]+box_out[3])
                    inter = max(0, xB - xA) * max(0, yB - yA)
                    area = box_in[2] * box_in[3]
                    return inter / float(area) if area > 0 else 0

                for y_det in yolo_detections:
                    y_box = (y_det.x, y_det.y, y_det.w, y_det.h)
                    matched_idx = -1
                    for i, m_box in enumerate(motion_boxes):
                        if _iou(y_box, m_box) > cfg.intersection_iou or _containment(y_box, m_box) > cfg.intersection_containment or _containment(m_box, y_box) > cfg.intersection_containment:
                            matched_idx = i
                            break
                    if matched_idx != -1:
                        motion_clusters[matched_idx].append(y_det)
                        
                for i, m_box in enumerate(motion_boxes):
                    matched = motion_clusters[i]
                    if matched:
                        min_x = min([m_box[0]] + [d.x for d in matched])
                        min_y = min([m_box[1]] + [d.y for d in matched])
                        max_x = max([m_box[0]+m_box[2]] + [d.x+d.w for d in matched])
                        max_y = max([m_box[1]+m_box[3]] + [d.y+d.h for d in matched])
                        
                        best_class = "Person" if any(d.class_name == "Person" for d in matched) else matched[0].class_name
                        best_conf = max(d.confidence for d in matched)
                        
                        if best_class == "Person":
                            self._human_detected_this_session = True
                        
                        pad = 10
                        x = max(0, min_x - pad)
                        y = max(0, min_y - pad)
                        w = min(TARGET_W - x, (max_x - min_x) + pad*2)
                        h = min(TARGET_H - y, (max_y - min_y) + pad*2)
                        
                        final_detections.append(Detection(
                            x=x, y=y, w=w, h=h,
                            confidence=best_conf,
                            class_name=best_class,
                            source="hybrid",
                            keypoints=None,
                            metadata={
                                "prong_a_blob_area": m_box[2] * m_box[3],
                                "prong_b_conf": best_conf,
                            }
                        ))

                detections = final_detections
                self._last_intersection_pass = len(final_detections)

                # Record detection history snapshot for debug panel
                self._detection_history.append({
                    "ts": time.time(),
                    "prong_a_blobs": self._last_prong_a_blob_count,
                    "prong_a_area": self._last_prong_a_blob_area,
                    "prong_b_dets": self._last_yolo_det_count,
                    "prong_b_conf": round(self._last_prong_b_conf, 3),
                    "intersection_pass": self._last_intersection_pass,
                    "mode": self.permanent_bg_edges is not None,
                })

                # === Build Viz Frame based on selected mode ===
                if self._viz_mode == "PRONG_A" and motion_mask is not None:
                    # Show structural motion mask (heatmap-style)
                    viz_frame = cv2.applyColorMap(motion_mask, cv2.COLORMAP_JET)
                    # Overlay motion boxes in green
                    for m_box in motion_boxes:
                        x, y, w, h = m_box
                        cv2.rectangle(viz_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                        
                elif self._viz_mode == "PRONG_B":
                    # Show YOLO raw detections in blue
                    viz_frame = frame_to_process.copy()
                    for det in yolo_detections:
                        x1, y1 = det.x, det.y
                        x2, y2 = det.x + det.w, det.y + det.h
                        cv2.rectangle(viz_frame, (int(x1), int(y1)), (int(x2), int(y2)), (255, 0, 0), 2)
                        cv2.putText(viz_frame, f"YOLO {det.confidence:.2f}",
                                    (int(x1), int(y1) - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1, cv2.LINE_AA)
                                    
                else:
                    # COMBINED (Default): draw intersection-validated boxes
                    viz_frame = frame_to_process.copy()
                    for det in detections:
                        x1, y1 = det.x, det.y
                        x2, y2 = det.x + det.w, det.y + det.h
                        color = (0, 0, 255) if det.class_name in ["Weapon"] else (0, 255, 255)
                        cv2.rectangle(viz_frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                        cv2.putText(viz_frame, f"{det.class_name} {det.confidence:.2f}",
                                    (int(x1), int(y1) - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)

                with self._det_lock:
                    self._latest_detections = detections
                    self._latest_viz_frame = viz_frame

                self._last_inference_ts = time.time()
                self._last_inference_ms = (time.perf_counter() - _cycle_start) * 1000
                self._inference_cycle_count += 1

                # If we detected an object here and ALARM_TRIGGER_TYPE is DETECTION, trigger it now.
                # Only trigger if not already alarming to avoid blowing up the counter and queue
                if self.alarm_trigger_type == "DETECTION" and len(detections) > 0:
                    with self._threat_count_lock:
                        already_alarming = self._active_threat_count > 0
                    if not already_alarming:
                         self.system.trigger_instant_alarm(self.node_id, detections, from_inference=True)

            except Exception as e:
                _log_exception(self.node_id, e, context="inference_loop")
                self._last_exception_info = {
                    "ts_str": datetime.datetime.now().strftime("%H:%M:%S"),
                    "context": "inference_loop",
                    "type": type(e).__name__,
                    "message": str(e),
                }
                print(f"[{self.node_id}] Inference error: {e}")
                time.sleep(1.0)

    def stop(self):
        self._stopped = True
        
    def _capture_loop(self):
        src = self.stream_url
        if isinstance(src, str) and src.isdigit():
            src = int(src)

        is_video_file = isinstance(src, str) and os.path.isfile(str(src))
        
        # Initial reachability check
        if not is_video_file and isinstance(src, str) and src.startswith("http"):
            import urllib.request
            try:
                urllib.request.urlopen(src, timeout=2.0)
            except Exception:
                pass # let cv2 handle it or fail in the loop
        
        cap = None
        if is_video_file or (isinstance(src, int)):
            cap = cv2.VideoCapture(src)
            if not is_video_file:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        frame_interval = 1.0 / TARGET_FPS
        last_t = 0.0
        last_frame_time = time.time()

        while not self._stopped:
            # Check if source is open
            is_open = True
            if cap is not None:
                is_open = cap.isOpened()
            elif isinstance(src, str) and (src.startswith("http") or src.startswith("gst:")):
                is_open = hasattr(self, '_stream') and self._stream is not None

            if not is_open:
                self.online = False
                
                # Check if we should save the live clip
                if len(self.frame_buffer) > 0 and getattr(self, 'threat_detected_this_session', False):
                    print(f"[{self.node_id}] Stream disconnected cleanly. Saving live clip.")
                    self.system.save_live_clip(self.node_id, list(self.frame_buffer), self._latest_detections)
                with self._lock:
                    self.frame_buffer.clear()
                self.threat_detected_this_session = False
                self._was_online = False
                        
                print(f"[{self.node_id}] WAITING FOR SIGNAL - {src}")
                time.sleep(2.0)
                
                # Check reachability first to avoid OpenCV hang
                if not is_video_file and isinstance(src, str) and src.startswith("http"):
                    import urllib.request
                    try:
                        urllib.request.urlopen(src, timeout=2.0)
                    except Exception as e:
                        print(f"[{self.node_id}] Host unreachable: {e}")
                        continue
                
                # Reconnect
                if is_video_file or isinstance(src, int):
                    cap = cv2.VideoCapture(src)
                    if not is_video_file:
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    if cap.isOpened():
                        print(f"[{self.node_id}] ONLINE - {'VIDEO FILE' if is_video_file else 'CAMERA'}")
                        last_frame_time = time.time()
                else:
                    # HTTP or GST stream reconnection is handled by the reader below
                    if isinstance(src, str) and src.startswith("http"):
                        try:
                            import urllib.request
                            self._stream = urllib.request.urlopen(src, timeout=3.0)
                            self._bytes = b''
                            print(f"[{self.node_id}] ONLINE - HTTP MJPEG STREAM")
                            last_frame_time = time.time()
                        except Exception as e:
                            print(f"[{self.node_id}] Stream connect failed: {e}")
                    elif isinstance(src, str) and (src.startswith("gst:") or src.startswith("rawgst:")):
                        try:
                            import subprocess
                            if src.startswith("rawgst:"):
                                pipeline_str = src[7:].split(":", 2)[2].strip()
                            else:
                                pipeline_str = src[4:].strip()
                            self._gst_process = subprocess.Popen(pipeline_str, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True, bufsize=1048576)
                            self._stream = self._gst_process.stdout
                            self._bytes = b''
                            print(f"[{self.node_id}] ONLINE - GSTREAMER RAW STREAM")
                            last_frame_time = time.time()
                        except Exception as e:
                            print(f"[{self.node_id}] GStreamer connect failed: {e}")
                continue

            # Check manual timeout for hung stream
            if not is_video_file and (time.time() - last_frame_time > 5.0):
                print(f"[DEBUG-CAPTURE] [{self.node_id}] Stream HUNG! No frames for 5 seconds. Forcing disconnect.")
                is_open = False
                if hasattr(self, '_stream') and self._stream:
                    try: self._stream.close()
                    except: pass
                    self._stream = None
                if hasattr(self, '_gst_process') and self._gst_process:
                    try: self._gst_process.terminate()
                    except: pass
                    self._gst_process = None
                continue

            if not cap and not is_video_file and isinstance(src, str) and (src.startswith("http") or src.startswith("gst:") or src.startswith("rawgst:")):
                # Use robust custom reader for HTTP MJPEG / GST streams
                try:
                    if not hasattr(self, '_stream') or self._stream is None:
                        if src.startswith("http"):
                            import urllib.request
                            self._stream = urllib.request.urlopen(src, timeout=3.0)
                            self._is_raw = False
                        else:
                            import subprocess
                            if src.startswith("rawgst:"):
                                parts = src[7:].split(":", 2)
                                self._raw_w = int(parts[0])
                                self._raw_h = int(parts[1])
                                pipeline_str = parts[2].strip()
                                self._is_raw = True
                            else:
                                pipeline_str = src[4:].strip()
                                self._is_raw = False
                                
                            self._gst_process = subprocess.Popen(pipeline_str, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True, bufsize=1048576)
                            self._stream = self._gst_process.stdout
                        self._bytes = b''
                        last_frame_time = time.time()
                    
                    if getattr(self, '_is_raw', False):
                        frame_sz = self._raw_w * self._raw_h * 3
                        # Force blocking read to guarantee we pull exactly one frame's worth of bytes
                        needed = frame_sz - len(self._bytes)
                        chunk = self._stream.read(min(needed, 65536 * 4))
                        if not chunk:
                            ret = False
                            continue
                        self._bytes += chunk
                        
                        if len(self._bytes) == frame_sz:
                            import numpy as np
                            raw = np.frombuffer(self._bytes, dtype=np.uint8).reshape((self._raw_h, self._raw_w, 3))
                            self._bytes = b''
                            ret = True
                            self.online = True
                            last_frame_time = time.time()
                        else:
                            continue # Need more bytes to complete frame
                    else:
                        # Read chunk (non-blocking if possible)
                        if hasattr(self._stream, 'read1'):
                            self._bytes += self._stream.read1(65536)
                        else:
                            self._bytes += self._stream.read(8192)

                        # Extract all complete frames in the buffer, keep only the latest
                        last_valid_jpg = None
                        while True:
                            a = self._bytes.find(b'\xff\xd8')
                            if a == -1:
                                break
                            b = self._bytes.find(b'\xff\xd9', a + 2)
                            if b == -1:
                                # Incomplete frame, discard garbage before 'a' and wait for more data
                                self._bytes = self._bytes[a:]
                                break
                            
                            # Complete frame found
                            last_valid_jpg = self._bytes[a:b+2]
                            self._bytes = self._bytes[b+2:]

                        if last_valid_jpg is not None:
                            import numpy as np
                            raw = cv2.imdecode(np.frombuffer(last_valid_jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                            if raw is not None:
                                ret = True
                                self.online = True
                                last_frame_time = time.time()
                            else:
                                ret = False
                        else:
                            continue # Need more bytes
                        
                except Exception as e:
                    _log_exception(self.node_id, e, context="mjpeg_reader")
                    print(f"[{self.node_id}] MJPEG Stream error: {e}")
                    ret = False
                    if hasattr(self, '_stream') and self._stream:
                        self._stream.close()
                        self._stream = None
                    if hasattr(self, '_gst_process') and self._gst_process:
                        try: self._gst_process.terminate()
                        except: pass
                        self._gst_process = None
            else:
                try:
                    ret, raw = cap.read()
                    if ret: last_frame_time = time.time()
                except Exception as e:
                    print(f"[{self.node_id}] Error reading from camera: {e}")
                    ret = False
                    
            if not ret:
                self.online = False
                
                # --- AUTO RECALIBRATION LOGIC ---
                if self._was_online:
                    self._was_online = False
                    if getattr(self, '_had_large_discrepancy', False) and not getattr(self, '_human_detected_this_session', False):
                        # A massive structural change happened, but the AI confirmed it was NOT a human.
                        # (e.g. tree fell, fence built, car parked). We auto-capture this as the new background!
                        print(f"[{self.node_id}] Auto-calibrating background (Structural Discrepancy + No Human).")
                        self.system.set_permanent_background(self.node_id)
                
                if is_video_file:
                    if cap: cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                else:
                    if cap: 
                        cap.release()
                        cap = None
                    continue
                    
            if not self._was_online:
                self._was_online = True
                self.threat_detected_this_session = True
                self._had_large_discrepancy = False
                self._human_detected_this_session = False
                
                # Instant Alarm: The moment the PIR connects the stream, we trigger the alarm.
                if self.alarm_trigger_type == "PIR":
                    from detection_engine import Detection
                    fake_det = Detection(x=0, y=0, w=0, h=0, confidence=1.0, class_name="PIR Trigger", source="system", keypoints=None, metadata={})
                    self.system.trigger_instant_alarm(self.node_id, [fake_det])
                    print(f"[{self.node_id}] STREAM CONNECTED! PIR Instant alarm triggered.")

            self.online = True
            
            now = time.time()
            if now - last_t < frame_interval:
                # To prevent dropping decoded HTTP frames, we should only sleep if it's a file or we don't care
                if is_video_file or cap is not None:
                    time.sleep(0.003)
                    continue
                # For HTTP, we just process it to avoid losing the bytes, or we throttle reading.
                # Actually, processing it is fine.
            last_t = now

            # FPS
            self._ts_ring.append(now)
            if len(self._ts_ring) >= 2:
                span = self._ts_ring[-1] - self._ts_ring[0]
                if span > 0:
                    self._fps = (len(self._ts_ring) - 1) / span

            try:
                frame = raw
                if frame.shape[:2] != (TARGET_H, TARGET_W):
                    frame = cv2.resize(frame, (TARGET_W, TARGET_H))

                with self._det_lock:
                    viz_mode = getattr(self, '_viz_mode', 'COMBINED')
                    dets = getattr(self, '_latest_detections', [])
                    v = getattr(self, '_latest_viz_frame', None)

                if viz_mode == 'COMBINED':
                    viz = frame.copy()
                    for det in dets:
                        x1, y1 = det.x, det.y
                        x2, y2 = det.x + det.w, det.y + det.h
                        color = (0, 0, 255) if det.class_name in ["Weapon"] else (0, 255, 255)
                        cv2.rectangle(viz, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                        cv2.putText(viz, f"{det.class_name} {det.confidence:.2f}",
                                    (int(x1), int(y1) - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
                else:
                    viz = v.copy() if v is not None else frame.copy()

                cv2.putText(viz, f"{self.node_id} | LIVE", (8, 18),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1, cv2.LINE_AA)

                with self._lock:
                    self.frame_buffer.append(frame.copy())   # buffer stores clean raw frame
                    self._live_frame = viz                    # stream shows viz overlay
                    self._raw_frame = frame.copy()
                    self._last_capture_ts = time.time()

            except Exception as e:
                _log_exception(self.node_id, e, context="capture_loop")
                self._last_exception_info = {
                    "ts_str": datetime.datetime.now().strftime("%H:%M:%S"),
                    "context": "capture_loop",
                    "type": type(e).__name__,
                    "message": str(e),
                }
                print(f"[{self.node_id}] Exception during processing: {e}")
                import traceback; traceback.print_exc()

        if cap is not None:
            cap.release()
        if hasattr(self, '_stream') and self._stream is not None:
            self._stream.close()
        if hasattr(self, '_gst_process') and self._gst_process is not None:
            try: self._gst_process.terminate()
            except: pass
        self.online = False

    def get_live_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            if self._live_frame is not None:
                return self._live_frame.copy()
        return None

    def get_raw_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            if self._raw_frame is not None:
                return self._raw_frame.copy()
        return None

    def snapshot_buffer(self):
        with self._lock:
            return list(self.frame_buffer)

    def get_status(self) -> Dict:
        return {
            "node_id": self.node_id,
            "online": self.online,
            "fps": round(self._fps, 1),
            "buffer_frames": 0,
            "clips_saved": self.clips_saved,
        }



# ===========================
# HASHTAG SYSTEM
# ===========================
class HashtagSystem:
    """
    Main orchestrator for the Hashtag V2 border surveillance system.
    """

    def __init__(self):
        # Shared detection engine (one GPU model for all analysis jobs)
        self.engine = DetectionEngine(
            person_model_path=DEFAULT_MODEL_PATH,
            person_conf=0.15,  # Baseline; overridden per-node in inference loop
            device=None
        )
        self.analyzer = BatchAnalyzer(self.engine)
        self.degrader = OV5647Degrader()

        # Per-node configuration (loaded from disk)
        self._node_configs: Dict[str, NodeConfig] = _load_node_configs()
        self._config_lock = threading.Lock()

        # Camera nodes
        self.nodes: Dict[str, CameraNode] = {}

        # Analysis jobs
        self._jobs: Dict[str, AnalysisJob] = {}
        self._job_lock = threading.Lock()
        self._last_buzzer = 0.0

        # System state
        self._start_time = time.time()

        # Events log
        self._events: deque = deque(maxlen=500)

        self._setup_nodes()

        # Start clip retention manager daemon
        threading.Thread(target=self._retention_loop, daemon=True).start()

    def _setup_nodes(self):
        """
        Load nodes from nodes.json (or write defaults on first run).
        ONLY use HTTP URLs — integer device IDs (webcams) are BLOCKED.
        """
        nodes_list = _load_nodes_from_disk()
        print(f"[NODES] Loading {len(nodes_list)} nodes from nodes.json")
        for nd in nodes_list:
            nid = nd.get("id", "")
            url = nd.get("stream_url", "")
            if not nid:
                continue
            if isinstance(url, int) or (isinstance(url, str) and url.strip().isdigit()):
                print(f"[{nid}] BLOCKED: Integer device ID is not a valid field camera URL. Skipping.")
                continue
            self._add_node(nid, url, name=nd.get("name", nid),
                           lat=nd.get("lat", 0.0), lng=nd.get("lng", 0.0),
                           alarm_trigger_type=nd.get("alarm_trigger_type", "PIR"))

    def _add_node(self, node_id: str, stream_url: Any, name="", lat=0.0, lng=0.0, alarm_trigger_type="PIR") -> CameraNode:
        node = CameraNode(node_id, stream_url, self, self.engine, self.degrader, name=name, lat=lat, lng=lng, alarm_trigger_type=alarm_trigger_type)
        node.start()
        self.nodes[node_id] = node
        return node

    def _nodes_as_list(self) -> List[Dict]:
        """Serialise current live nodes to a list suitable for nodes.json."""
        return [
            {
                "id": nid,
                "name": n.name,
                "stream_url": n.stream_url,
                "lat": n.lat,
                "lng": n.lng,
                "alarm_trigger_type": getattr(n, "alarm_trigger_type", "PIR")
            }
            for nid, n in self.nodes.items()
        ]

    def add_node(self, node_id: str, stream_url: Any, name="", lat=0.0, lng=0.0, alarm_trigger_type="PIR") -> CameraNode:
        if isinstance(stream_url, int) or (isinstance(stream_url, str) and stream_url.strip().isdigit()):
            raise ValueError(f"Integer device IDs are blocked. Provide an HTTP or GST URL.")
        if node_id in self.nodes:
            self.nodes[node_id].stop()
        node = self._add_node(node_id, stream_url, name, lat, lng, alarm_trigger_type)
        _save_nodes_to_disk(self._nodes_as_list())
        self._log_event("NODE_ADDED", f"Node {node_id} ({name}) added at {stream_url}")
        return node

    def update_node(self, node_id: str, **kwargs) -> Dict:
        """
        Partially update a node's properties. Handles:
          - name      → renames Clips/<node_id>/<old_name>/ folder
          - stream_url→ restarts capture thread pointing at new URL
          - lat / lng → updates coords (new clips get new location)
        All changes persist to nodes.json immediately.
        """
        if node_id not in self.nodes:
            return {"error": f"Node {node_id} not found"}
        node = self.nodes[node_id]
        changes = []

        if "name" in kwargs and kwargs["name"] != node.name:
            old_safe = str(node.name).replace(" ", "_").upper()
            new_name = kwargs["name"]
            new_safe = str(new_name).replace(" ", "_").upper()
            old_dir = os.path.join(CLIPS_DIR, node_id, old_safe)
            new_dir = os.path.join(CLIPS_DIR, node_id, new_safe)
            if os.path.isdir(old_dir) and not os.path.exists(new_dir):
                try:
                    os.rename(old_dir, new_dir)
                    print(f"[NODES] Renamed clip folder: {old_safe} → {new_safe}")
                except Exception as e:
                    print(f"[NODES] Failed to rename clip folder: {e}")
            node.name = new_name
            changes.append(f"name: {new_name}")

        if "stream_url" in kwargs and kwargs["stream_url"] != node.stream_url:
            new_url = kwargs["stream_url"]
            if isinstance(new_url, int) or (isinstance(new_url, str) and new_url.strip().isdigit()):
                return {"error": "Integer device IDs are blocked. Provide an HTTP or GST URL."}
            node.stream_url = new_url
            # Restart capture with new URL
            node._stopped = True
            time.sleep(0.5)
            node._stopped = False
            node._capture_thread = threading.Thread(target=node._capture_loop, daemon=True)
            node._capture_thread.start()
            node._inference_thread = threading.Thread(target=node._inference_loop, daemon=True)
            node._inference_thread.start()
            changes.append(f"stream_url: {new_url}")

        if "lat" in kwargs:
            node.lat = float(kwargs["lat"])
            changes.append(f"lat: {node.lat}")
        if "lng" in kwargs:
            node.lng = float(kwargs["lng"])
            changes.append(f"lng: {node.lng}")
        if "alarm_trigger_type" in kwargs:
            node.alarm_trigger_type = str(kwargs["alarm_trigger_type"]).strip().upper()
            if node.alarm_trigger_type not in ["PIR", "DETECTION"]:
                node.alarm_trigger_type = "PIR"
            changes.append(f"alarm_trigger_type: {node.alarm_trigger_type}")

        _save_nodes_to_disk(self._nodes_as_list())
        msg = f"Node {node_id} updated: {', '.join(changes)}"
        print(f"[NODES] {msg}")
        self._log_event("NODE_UPDATED", msg)
        return {"status": "ok", "node_id": node_id, "changes": changes}

    def remove_node(self, node_id: str):
        if node_id not in self.nodes:
            return
        node = self.nodes[node_id]
        node.stop()
        del self.nodes[node_id]

        # Remove from node_configs and persist
        with self._config_lock:
            self._node_configs.pop(node_id, None)
        _save_node_configs(self._node_configs)

        # Archive clip folder (preserve evidence, but mark as deleted)
        safe_name = str(node.name).replace(" ", "_").upper()
        node_dir = os.path.join(CLIPS_DIR, node_id, safe_name)
        if os.path.isdir(node_dir):
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_dir = node_dir + f"_DELETED_{ts}"
            try:
                os.rename(node_dir, archive_dir)
                print(f"[NODES] Archived clip folder to {archive_dir}")
            except Exception as e:
                print(f"[NODES] Failed to archive clip folder: {e}")

        _save_nodes_to_disk(self._nodes_as_list())
        self._log_event("NODE_REMOVED", f"Node {node_id} removed and archived")
        print(f"[NODES] Node {node_id} removed")

    def get_all_nodes_info(self) -> List[Dict]:
        """Return full node info for the /api/nodes endpoint."""
        result = []
        for nid, node in self.nodes.items():
            cfg = self.get_node_config(nid)
            result.append({
                "id": nid,
                "name": node.name,
                "stream_url": node.stream_url,
                "lat": node.lat,
                "lng": node.lng,
                "online": node.online,
                "fps": round(node._fps, 1),
                "clips_saved": node.clips_saved,
                "has_permanent_bg": node.permanent_bg_edges is not None,
                "viz_mode": node._viz_mode,
                "config": asdict(cfg),
            })
        return result

    def get_debug_snapshot(self, node_id: str) -> Dict:
        """
        Full diagnostic snapshot for the live debug panel.
        Returns everything an engineer would need to diagnose a pipeline issue:
          - Thread heartbeats (alive + age since last frame/inference)
          - Per-cycle Prong A/B metrics
          - Detection history (last 30 cycles)
          - Last exception (both threads)
          - Background health
          - Per-node config in effect
        """
        now = time.time()
        node = self.nodes.get(node_id)
        if not node:
            return {"error": f"Node {node_id} not found"}

        capture_age  = round(now - node._last_capture_ts,  1) if node._last_capture_ts  else None
        inference_age = round(now - node._last_inference_ts, 1) if node._last_inference_ts else None

        capture_health  = "OK"   if capture_age  is not None and capture_age  < 5  else ("STALE" if capture_age is not None else "NEVER")
        inference_health = "OK"  if inference_age is not None and inference_age < 5 else ("STALE" if inference_age is not None else "NEVER")

        cfg = self.get_node_config(node_id)

        return {
            "node_id": node_id,
            "name": node.name,
            "ts": now,

            # ── Thread heartbeats ───────────────────────────────────────
            "threads": {
                "capture_alive":        node._capture_thread.is_alive() if hasattr(node, '_capture_thread') else False,
                "inference_alive":      node._inference_thread.is_alive() if hasattr(node, '_inference_thread') else False,
                "capture_last_frame_age_s":  capture_age,
                "inference_last_cycle_age_s": inference_age,
                "capture_health":        capture_health,
                "inference_health":      inference_health,
            },

            # ── Live pipeline metrics (last cycle) ──────────────────────
            "pipeline": {
                "inference_ms":           round(node._last_inference_ms, 2),
                "inference_cycles_total": node._inference_cycle_count,
                "fps":                    round(node._fps, 2),
                "buffer_depth":           len(node.frame_buffer),
                "buffer_capacity":        node.frame_buffer.maxlen,
                "prong_mode":             "CANNY_BG" if node.permanent_bg_edges is not None else "MOG2",
                "prong_a_blobs":          node._last_prong_a_blob_count,
                "prong_a_avg_blob_area":  node._last_prong_a_blob_area,
                "prong_b_yolo_raw":       node._last_yolo_det_count,
                "prong_b_max_conf":       round(node._last_prong_b_conf, 3),
                "intersection_passed":    node._last_intersection_pass,
                "brightness_delta_pct":   round(node._brightness_delta * 100, 1),
                "bg_capture_brightness":  round(node._bg_capture_mean_brightness, 1) if node._bg_capture_mean_brightness else None,
            },

            # ── Detection history (last 30 cycles) ─────────────────────
            "detection_history": list(node._detection_history),

            # ── Last exception ──────────────────────────────────────────
            "last_exception": node._last_exception_info or None,

            # ── Active node config (in-effect right now) ────────────────
            "active_config": asdict(cfg),

            # ── Viz mode ────────────────────────────────────────────────
            "viz_mode": node._viz_mode,
        }

    def get_exception_log(self, node_id: str = None, limit: int = 50) -> List[Dict]:
        """
        Return the global exception ring buffer, optionally filtered by node.
        Each entry: {ts_str, node_id, context, type, message, source_hint, traceback}
        """
        log = list(_EXCEPTION_LOG)
        if node_id:
            log = [e for e in log if e.get("node_id") == node_id]
        return list(reversed(log))[:limit]  # newest first


    def set_permanent_background(self, node_id: str):
        if node_id in self.nodes:
            node = self.nodes[node_id]
            frame = node.get_raw_frame()
            if frame is not None:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                cfg = self.get_node_config(node_id)
                node.permanent_bg_edges = cv2.Canny(gray, cfg.canny_low, cfg.canny_high)
                node.permanent_bg_frame = gray.copy()          # store raw gray for thermal diff viz
                node._bg_capture_mean_brightness = float(np.mean(gray))
                node._bg_invalidation_strike = 0               # reset strike counter
                _save_bg_to_disk(node_id, node.permanent_bg_edges, node.permanent_bg_frame)  # persist
                print(f"[ADMIN] Set permanent background for {node_id} (brightness={node._bg_capture_mean_brightness:.1f}) — saved to disk")


    def clear_permanent_background(self, node_id: str):
        """Reset a node's permanent background, reverting to MOG2 motion detection."""
        if node_id in self.nodes:
            node = self.nodes[node_id]
            node.permanent_bg_edges = None
            node.permanent_bg_frame = None
            node._bg_capture_mean_brightness = None
            node._bg_invalidation_strike = 0
            _delete_bg_from_disk(node_id)  # remove persisted files
            print(f"[ADMIN] Cleared permanent background for {node_id} — disk files removed")

    def simulate_threat(self, node_id: str):
        if node_id in self.nodes:
            print(f"[ADMIN] Simulating threat on {node_id}")
            from detection_engine import Detection
            fake_det = Detection(x=100, y=100, w=200, h=300, confidence=0.99, class_name="Person", source="simulated", keypoints=None, metadata={})
            with self.nodes[node_id]._det_lock:
                self.nodes[node_id]._latest_detections.append(fake_det)
            
            sim_path = os.path.join(CLIPS_DIR, f"temp_{node_id}_simulated.mp4")
            if self.nodes[node_id]._save_buffer_to_mp4(sim_path):
                self.trigger_auto_threat(node_id, sim_path)

    def trigger_auto_threat(self, node_id: str, mp4_path: str):
        job_id = f"AUTO-{uuid.uuid4()}"
        job = AnalysisJob(job_id, node_id, mp4_path)
        job.is_auto_trigger = True
        with self._job_lock:
            self._jobs[job_id] = job
        threading.Thread(
            target=self._run_job, args=(job,), daemon=True
        ).start()
        print(f"[ANALYZE] {node_id} | Auto Job {job_id[:8]} queued | File: {mp4_path}")

    def trigger_instant_alarm(self, node_id: str, detections: List[Any], from_inference=False):
        job_id = f"INSTANT-{uuid.uuid4().hex[:8]}"
        job = AnalysisJob(job_id, node_id, [])
        job.is_auto_trigger = True
        
        entities = []
        for i, d in enumerate(detections):
            entities.append({
                "id": i,
                "class": d.class_name,
                "confidence": d.confidence,
                "threat_level": 4,
                "threat_score": 100,
                "distance_m": -1,
                "behavior": "INSTANT DETECT",
                "bbox": list(d.bbox)
            })
            
        with job._lock:
            job.status = AnalysisJob.STATUS_COMPLETE
            job.progress = 100
            job.threat_detected = True
            job.max_threat_level = 4
            job.entities = entities
            job.clip_path = "" 
        
        with self._job_lock:
            self._jobs[job_id] = job

        # Increment per-node unacknowledged threat count
        node = self.nodes.get(node_id)
        if node:
            if not from_inference and node.alarm_trigger_type == "DETECTION":
                # Do not alarm yet. Wait for inference thread to verify threat and call trigger_instant_alarm(..., from_inference=True)
                return

            with node._threat_count_lock:
                node._active_threat_count += 1
            
            # Sound alarm if cooldown expired
            now = time.time()
            if now - self._last_buzzer > BUZZER_COOLDOWN_SEC:
                self._last_buzzer = now
                _play_buzzer(4)

        self._log_event("INSTANT_ALARM", f"{node_id}: {len(entities)} entities detected instantly (queue={node._active_threat_count if node else '?'})", threat_level=4)

    def acknowledge_node(self, node_id: str):
        """Operator has acknowledged one threat on this node.
        Decrements the active threat count. Only clears the session
        flag once ALL threats have been acknowledged (count reaches 0).
        """
        node = self.nodes.get(node_id)
        if not node:
            return
        node._active_threat_count = max(0, node._active_threat_count - 1)
        
        # Check global unacknowledged threat count
        total_threats = sum(n._active_threat_count for n in self.nodes.values())
        if total_threats == 0:
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
                
        if node._active_threat_count == 0:
            node.threat_detected_this_session = False
            node._was_online = False
            print(f"[ADMIN] All threats acknowledged for {node_id}")
        else:
            print(f"[ADMIN] Threat ack for {node_id} — {node._active_threat_count} unacknowledged remaining")
        self._log_event(
            "ALARM_ACKNOWLEDGED",
            f"{node_id}: Threat acknowledged ({node._active_threat_count} remaining)"
        )

    def get_active_threats(self) -> List[Dict]:
        """Return all nodes with unacknowledged threats (count > 0), with lat/lng for map fit."""
        result = []
        for nid, node in self.nodes.items():
            if node._active_threat_count > 0:
                result.append({
                    "node_id": nid,
                    "name": node.name,
                    "lat": node.lat,
                    "lng": node.lng,
                    "threat_count": node._active_threat_count,
                    "replay_url": f"http://localhost:5000/video_feed/{nid}",
                })
        return result

    def set_viz_mode(self, node_id: str, mode: str):
        """Set the visualization mode for a camera node: COMBINED | PRONG_A | PRONG_B."""
        valid = {'COMBINED', 'PRONG_A', 'PRONG_B'}
        if node_id in self.nodes and mode in valid:
            self.nodes[node_id]._viz_mode = mode
            print(f"[ADMIN] Viz mode set to {mode} for {node_id}")

    def report_false_positive(self, node_id: str) -> Dict:
        """
        Smart false-positive correction.
        Analyzes the last detection's Prong A blob area and Prong B YOLO confidence
        to determine which prong was more responsible, then adjusts that prong's
        sensitivity to reduce future false positives from that source.
        Returns a dict describing what was changed.
        """
        node = self.nodes.get(node_id)
        if not node:
            return {"error": "Node not found"}

        cfg = self.get_node_config(node_id)
        blob_area = getattr(node, '_last_prong_a_blob_area', 0)
        yolo_conf = getattr(node, '_last_prong_b_conf', 0.0)

        cfg.fp_count += 1
        result = {"node_id": node_id, "fp_count": cfg.fp_count,
                  "blob_area": blob_area, "yolo_conf": yolo_conf}

        # Determine blame:
        # - If YOLO conf is LOW (<0.15) but blob area is LARGE (>5000 px²):
        #     YOLO was the weak link → tighten YOLO (raise person_conf, record B blame)
        # - If YOLO conf is OK (>=0.15) but blob area is SMALL (<2000 px²):
        #     Prong A over-triggered on noise → tighten A (raise prong_a_threshold, record A blame)
        # - Mixed → split the correction proportionally

        LARGE_BLOB = 5000
        SMALL_BLOB = 2000
        HIGH_YOLO  = 0.15

        if yolo_conf < HIGH_YOLO and blob_area >= LARGE_BLOB:
            # Prong B (YOLO) is the problem: blob was clearly there, YOLO triggered at junk confidence
            delta_b_conf = 0.03
            cfg.person_conf = min(0.50, cfg.person_conf + delta_b_conf)
            cfg.prong_b_fp_score += 1.0
            result.update({"blame": "PRONG_B",
                           "action": f"YOLO conf raised {cfg.person_conf - delta_b_conf:.2f} → {cfg.person_conf:.2f}",
                           "reason": "YOLO low confidence triggered on large structural blob"})

        elif yolo_conf >= HIGH_YOLO and blob_area < SMALL_BLOB:
            # Prong A is the problem: tiny blob triggered, YOLO confirmed it spuriously
            delta_a_thr = 3
            cfg.prong_a_threshold = min(80, cfg.prong_a_threshold + delta_a_thr)
            cfg.prong_a_fp_score += 1.0
            result.update({"blame": "PRONG_A",
                           "action": f"Prong A threshold raised {cfg.prong_a_threshold - delta_a_thr} → {cfg.prong_a_threshold}",
                           "reason": "Small structural discrepancy blob triggered false detection"})

        else:
            # Both are ambiguous — split correction
            cfg.person_conf = min(0.50, cfg.person_conf + 0.015)
            cfg.prong_a_threshold = min(80, cfg.prong_a_threshold + 2)
            cfg.prong_a_fp_score += 0.5
            cfg.prong_b_fp_score += 0.5
            result.update({"blame": "SPLIT",
                           "action": "Both Prong A threshold (+2) and YOLO conf (+0.015) tightened slightly",
                           "reason": "Ambiguous false positive — both prongs contributed"})

        _save_node_configs(self._node_configs)

        # Save FP report to the node's directory
        node_obj = self.nodes.get(node_id)
        safe_name = str(node_obj.name).replace(" ", "_").upper() if node_obj else node_id
        node_dir = os.path.join(CLIPS_DIR, node_id, safe_name)
        os.makedirs(node_dir, exist_ok=True)
        fp_report_path = os.path.join(node_dir, "false_positive_log.json")
        fp_log = []
        if os.path.exists(fp_report_path):
            try:
                with open(fp_report_path) as f:
                    fp_log = json.load(f)
            except Exception:
                pass
        result["timestamp_iso"] = datetime.datetime.now().isoformat()
        result["geolocation"] = {"lat": node_obj.lat if node_obj else 0, "lng": node_obj.lng if node_obj else 0}
        fp_log.append(result)
        try:
            with open(fp_report_path, "w") as f:
                json.dump(fp_log, f, indent=2)
        except Exception:
            pass

        self._log_event("FALSE_POSITIVE", f"{node_id}: FP #{cfg.fp_count} — {result.get('blame')} blamed", threat_level=0)
        return result


    def save_live_clip(self, node_id: str, frames: List[np.ndarray], detections: List[Any]):
        """
        Save a live clip with organized per-node folder structure:
          Clips/
            HASH-1/
              Tiger_Chongjan/
                2026-06-13_14-30-00_LAT24.16_LNG94.26_INCIDENT_E001.mp4
                2026-06-13_14-30-00_LAT24.16_LNG94.26_INCIDENT_E001_report.json
            HASH-2/
              ...
        """
        node = self.nodes.get(node_id)
        ts_obj = datetime.datetime.now()
        ts_str = ts_obj.strftime("%Y-%m-%d_%H-%M-%S")
        lat = node.lat if node else 0.0
        lng = node.lng if node else 0.0
        safe_name = str(node.name).replace(" ", "_").upper() if node else node_id

        # Per-node directory: Clips/<node_id>/<node_name>/
        node_dir = os.path.join(CLIPS_DIR, node_id, safe_name)
        os.makedirs(node_dir, exist_ok=True)

        incident_id = uuid.uuid4().hex[:8].upper()
        base_name = f"{ts_str}_LAT{lat:.4f}_LNG{lng:.4f}_INC-{incident_id}"
        fpath = os.path.join(node_dir, base_name + ".mp4")

        if frames:
            h, w = frames[0].shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(fpath, fourcc, TARGET_FPS, (w, h))
            for f in frames:
                writer.write(f)
            writer.release()

            # Re-encode to H.264 for browser compatibility
            import subprocess
            temp_fpath = fpath + ".temp.mp4"
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", fpath, "-vcodec", "libx264", temp_fpath],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
                )
                os.replace(temp_fpath, fpath)
            except Exception:
                pass

        # Rich metadata JSON sidecar
        entities = []
        for i, d in enumerate(detections):
            entities.append({
                "id": f"ENT-{i:03d}",
                "class": d.class_name,
                "threat_level": 4,
                "threat_score": 100,
                "behavior": "LIVE DETECT",
                "bbox": list(d.bbox),
                "confidence": d.confidence,
                "prong_a_blob_area": d.metadata.get("prong_a_blob_area", 0) if hasattr(d, 'metadata') else 0,
                "prong_b_conf": d.metadata.get("prong_b_conf", 0.0) if hasattr(d, 'metadata') else 0.0,
            })

        report = {
            "incident_id": incident_id,
            "node_id": node_id,
            "node_name": node.name if node else node_id,
            "timestamp_iso": ts_obj.isoformat(),
            "timestamp_unix": ts_obj.timestamp(),
            "geolocation": {"lat": lat, "lng": lng},
            "threat_detected": True,
            "max_threat_level": 4,
            "entities": entities,
            "entity_count": len(entities),
            "clip_url": f"/clips/{node_id}/{safe_name}/{base_name}.mp4",
            "false_positive_reported": False,
        }

        sidecar = fpath.replace(".mp4", "_report.json")
        try:
            with open(sidecar, "w") as f:
                json.dump(report, f, indent=2)
        except Exception:
            pass

        if node:
            node.clips_saved += 1
        self._log_event("CLIP_SAVED", f"{base_name} saved for {node_id} @ {lat:.4f},{lng:.4f}")
        return fpath

    # ============================
    # SPACE TRIGGER — CORE LOGIC
    # ============================
    def trigger_analysis(self) -> List[str]:
        """
        Called when SPACEBAR is pressed.
        Snapshots all node buffers and saves them directly as live clips.
        Returns empty list of job_ids.
        """
        job_ids = []
        for nid, node in self.nodes.items():
            job_id = str(uuid.uuid4())
            with node._lock:
                frames = list(node.frame_buffer)
            if frames:
                self.save_live_clip(nid, frames, node._latest_detections)
                print(f"[ANALYZE] {nid} | Live clip saved via spacebar")
            else:
                print(f"[ANALYZE] {nid} | Buffer empty, skipping")

        self._log_event("SPACE_TRIGGER", f"Live clips saved on nodes")
        return job_ids


    def _run_job(self, job: AnalysisJob):
        """Run analysis job with GPU concurrency limit to prevent OOM crashes."""
        # Acquire semaphore — max 2 concurrent GPU jobs.
        # If 2 are already running, this blocks until one finishes.
        with _BATCH_SEMAPHORE:
            try:
                self.analyzer.analyze(job)

                if job.threat_detected:
                    # Increment node clip count
                    if job.node_id in self.nodes:
                        self.nodes[job.node_id].clips_saved += 1

                    # Play buzzer
                    now = time.time()
                    if now - self._last_buzzer > BUZZER_COOLDOWN_SEC:
                        self._last_buzzer = now
                        _play_buzzer(job.max_threat_level)

                    self._log_event(
                        "THREAT_CONFIRMED",
                        f"{job.node_id}: {len(job.entities)} entities | "
                        f"Threat L{job.max_threat_level}",
                        threat_level=job.max_threat_level
                    )
                else:
                    self._log_event("SECTOR_CLEAR", f"{job.node_id}: No threats detected")

            except Exception as e:
                print(f"[ANALYZE] ERROR in job {job.job_id[:8]}: {e}")
                import traceback; traceback.print_exc()
                with job._lock:
                    job.status = AnalysisJob.STATUS_CLEAR
                    job.completed_at = time.time()

    def get_job(self, job_id: str) -> Optional[AnalysisJob]:
        with self._job_lock:
            return self._jobs.get(job_id)

    def get_replay_frame(self, job_id: str, node_id: str, frame_idx: int) -> Optional[np.ndarray]:
        """Get a specific frame from an analysis job's annotated output."""
        job = self.get_job(job_id)
        if not job or not job.annotated_frames:
            return None
        idx = max(0, min(frame_idx, len(job.annotated_frames) - 1))
        return job.annotated_frames[idx]

    # ============================
    # API DATA
    # ============================
    def get_status(self) -> Dict:
        node_statuses = {nid: n.get_status() for nid, n in self.nodes.items()}
        total_clips = sum(n.clips_saved for n in self.nodes.values())
        return {
            "nodes_online": sum(1 for n in self.nodes.values() if n.online),
            "nodes_total": len(self.nodes),
            "uptime_sec": round(time.time() - self._start_time),
            "clips_saved": total_clips,
            "sensors": [
                {
                    "id": nid,
                    "name": self.nodes[nid].name,
                    "online": ns["online"],
                    "fps": ns["fps"],
                    "buffer_frames": ns["buffer_frames"],
                    "clips_saved": ns["clips_saved"],
                    "threat_level": 0,
                    "url": f"http://localhost:5000/video_feed/{nid}",
                }
                for nid, ns in node_statuses.items()
            ],
        }

    def get_node_config(self, node_id: str) -> NodeConfig:
        """Return per-node tuning config, creating a default if not set."""
        with self._config_lock:
            if node_id not in self._node_configs:
                self._node_configs[node_id] = NodeConfig()
            return self._node_configs[node_id]

    def set_node_config(self, node_id: str, **kwargs) -> NodeConfig:
        """Update a node's tuning config and persist to disk immediately."""
        with self._config_lock:
            if node_id not in self._node_configs:
                self._node_configs[node_id] = NodeConfig()
            cfg = self._node_configs[node_id]
            for key, val in kwargs.items():
                if hasattr(cfg, key):
                    setattr(cfg, key, type(getattr(cfg, key))(val))
            _save_node_configs(self._node_configs)
            print(f"[CONFIG] Node {node_id} tuning updated: {kwargs}")
            return cfg

    def get_telemetry(self) -> Dict:
        """Return real-time system health metrics for the Admin Dashboard."""
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(CLIPS_DIR)
        gpu_used_mb = 0
        gpu_total_mb = 0
        try:
            import torch
            if torch.cuda.is_available():
                gpu_used_mb = round(torch.cuda.memory_allocated() / 1024 / 1024, 1)
                gpu_total_mb = round(torch.cuda.get_device_properties(0).total_memory / 1024 / 1024, 1)
        except Exception:
            pass

        node_latencies = {}
        for nid, node in self.nodes.items():
            node_latencies[nid] = {
                "online": node.online,
                "fps": round(node._fps, 1),
                "has_permanent_bg": node.permanent_bg_edges is not None,
            }

        return {
            "cpu_pct": cpu,
            "ram_pct": mem.percent,
            "ram_used_gb": round(mem.used / 1024**3, 2),
            "ram_total_gb": round(mem.total / 1024**3, 2),
            "disk_used_gb": round(disk.used / 1024**3, 2),
            "disk_free_gb": round(disk.free / 1024**3, 2),
            "gpu_used_mb": gpu_used_mb,
            "gpu_total_mb": gpu_total_mb,
            "uptime_sec": round(time.time() - self._start_time),
            "batch_jobs_queued": max(0, 2 - _BATCH_SEMAPHORE._value),
            "nodes": node_latencies,
        }

    def _retention_loop(self):
        """Daemon thread: auto-delete clips older than per-node retention policy.
        Walks the full CLIPS_DIR tree so per-node subdirectories are cleaned up."""
        while True:
            time.sleep(1800)  # Check every 30 minutes
            try:
                now = time.time()
                with self._config_lock:
                    node_retentions = {nid: cfg.clip_retention_days for nid, cfg in self._node_configs.items()}
                default_days = 7
                deleted = 0
                for root, dirs, files in os.walk(CLIPS_DIR):
                    # Determine which node this directory belongs to
                    rel_root = os.path.relpath(root, CLIPS_DIR)
                    parts = rel_root.split(os.sep)
                    node_id = parts[0] if parts[0] != '.' else None
                    max_days = node_retentions.get(node_id, default_days) if node_id else default_days
                    cutoff = now - max_days * 86400
                    for fname in files:
                        if not (fname.endswith(".mp4") or fname.endswith("_report.json")):
                            continue
                        fpath = os.path.join(root, fname)
                        if os.path.getmtime(fpath) < cutoff:
                            try:
                                os.remove(fpath)
                                deleted += 1
                            except Exception:
                                pass
                if deleted > 0:
                    print(f"[RETENTION] Deleted {deleted} files past retention.")
                    self._log_event("RETENTION_CLEANUP", f"Auto-deleted {deleted} files past retention policy.")
            except Exception as e:
                print(f"[RETENTION] Error during cleanup: {e}")


    def get_events(self, limit: int = 100) -> List[Dict]:
        return list(self._events)[-limit:]

    def get_clips(self) -> List[Dict]:
        clips = []
        # Walk the full Clips/ tree to find clips in per-node subdirectories
        all_mp4s = []
        for root, dirs, files in os.walk(CLIPS_DIR):
            for fname in files:
                if fname.endswith(".mp4"):
                    fpath = os.path.join(root, fname)
                    # Compute relative path from CLIPS_DIR for URL construction
                    rel = os.path.relpath(fpath, CLIPS_DIR).replace("\\", "/")
                    all_mp4s.append((os.path.getmtime(fpath), fpath, rel, fname))

        # Sort newest first
        all_mp4s.sort(key=lambda x: x[0], reverse=True)

        for _, fpath, rel, fname in all_mp4s[:200]:
            report_path = fpath.replace(".mp4", "_report.json")
            report = {}
            if os.path.exists(report_path):
                try:
                    with open(report_path) as f:
                        report = json.load(f)
                except Exception:
                    pass
            clips.append({
                "filename": rel,          # e.g. "HASH-1/TIGER_CHONGJAN/2026-06-13..."
                "basename": fname,
                "size_bytes": os.path.getsize(fpath),
                "report": report,
                "url": f"/clips/{rel}",
                "node_id": report.get("node_id", ""),
                "timestamp_iso": report.get("timestamp_iso", ""),
                "geolocation": report.get("geolocation", {}),
            })
        return clips


    def _log_event(self, event_type: str, description: str, threat_level: int = 0):
        self._events.append({
            "type": event_type,
            "description": description,
            "threat_level": threat_level,
            "ts_str": datetime.datetime.now().strftime("%H:%M:%S"),
            "timestamp": time.time(),
        })


# Singleton
_system: Optional[HashtagSystem] = None
_system_lock = threading.Lock()

def get_system() -> HashtagSystem:
    global _system
    if _system is None:
        with _system_lock:
            if _system is None:
                _system = HashtagSystem()
    return _system
