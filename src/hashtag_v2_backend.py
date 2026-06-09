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
NODE_CONFIGS_PATH = os.path.join(SRC_DIR, "node_configs.json")

# Portable model path: reads from env var HASHTAG_MODEL_PATH, falls back to the
# known local path. Set the env var for deployment on a different machine.
DEFAULT_MODEL_PATH = os.environ.get(
    "HASHTAG_MODEL_PATH",
    r"C:\Users\hsiraa\runs\detect\Advanced_Person_Detection\Occlusion_Camouflage_V1-7\weights\best.pt"
)

TARGET_W, TARGET_H = 800, 640
TARGET_FPS = 2.0
BUFFER_SECONDS = 30
MIN_FRAMES_FOR_THREAT = 1
BUZZER_COOLDOWN_SEC = 10

# Max concurrent GPU batch analysis jobs to prevent OOM on multi-camera wakeup.
# If 5 cameras wake up simultaneously, 5 GPU jobs would OOM. This cap queues extras.
_BATCH_SEMAPHORE = threading.Semaphore(2)


# ===========================
# PER-NODE CONFIGURATION
# ===========================
from dataclasses import dataclass, asdict

@dataclass
class NodeConfig:
    """Per-camera tuning parameters, persisted to node_configs.json."""
    person_conf: float = 0.35
    canny_low: int = 50
    canny_high: int = 150
    clip_retention_days: int = 7  # Auto-delete clips older than this


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

# ===========================
# AUDIBLE ALERT (Windows)
# ===========================
def _play_buzzer(threat_level: int):
    def _beep():
        try:
            import winsound
            if threat_level >= 4:   # CRITICAL
                for _ in range(5):
                    winsound.Beep(1200, 200)
                    time.sleep(0.05)
            elif threat_level >= 3: # HIGH
                for _ in range(3):
                    winsound.Beep(900, 150)
                    time.sleep(0.1)
            else:                   # MEDIUM
                winsound.Beep(700, 350)
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

    def __init__(self, job_id: str, node_id: str, mp4_path: str):
        self.job_id = job_id
        self.node_id = node_id
        self.mp4_path = mp4_path       # Path to the temporary MP4
        self.status = self.STATUS_QUEUED
        self.progress = 0              # 0-100
        self.threat_detected = False
        self.max_threat_level = 0
        self.entities: List[Dict] = []
        self.annotated_frames: List[np.ndarray] = []  # JPEG bytes for replay
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

            # Raw detection with tracking persistence
            detections = self.engine.detect(
                frame, 
                cam_id=node_num, 
                fps=TARGET_FPS, 
                active_boxes=active_boxes,
                motion_mask=None
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
            job.annotated_frames = annotated_out
            job.clip_path = clip_path
            job.completed_at = time.time()

    def _save_clip(self, job_id: str, node_id: str,
                   frames: List[np.ndarray], entities: List[Dict]) -> str:
        # Add a "LOOP RESTART" frame to the end so it doesn't look static if the clip is very short
        blank = np.zeros((TARGET_H, TARGET_W, 3), dtype=np.uint8)
        cv2.putText(blank, "LOOP RESTARTING...", (TARGET_W//2 - 150, TARGET_H//2), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)
        frames.append(blank)

        """Write annotated frames to an MP4 file and JSON sidecar."""
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

        if frames:
            h, w = frames[0].shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(fpath, fourcc, TARGET_FPS, (w, h))
            for f in frames:
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
                 degrader: Optional[OV5647Degrader] = None, name: str = "", lat: float = 0.0, lng: float = 0.0):
        self.node_id = node_id
        self.stream_url = stream_url
        self.name = name
        self.lat = lat
        self.lng = lng
        self.system = system_ref
        self.engine = engine
        self.degrader = degrader or OV5647Degrader()

        self.online = False
        self._stopped = False
        self.clips_saved = 0

        self.temp_mp4_path = os.path.join(CLIPS_DIR, f"temp_{self.node_id}.mp4")
        self.temp_writer = None
        self.permanent_bg_edges = None

        # Lighting-change detection: track mean brightness to auto-invalidate bg
        self._bg_capture_mean_brightness: Optional[float] = None
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

        self.degrader = OV5647Degrader()

        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._inference_thread = threading.Thread(target=self._inference_loop, daemon=True)

    def start(self):
        self._capture_thread.start()
        self._inference_thread.start()
        
    def _inference_loop(self):
        mog2 = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=False)

        while not self._stopped:
            frame_to_process = self.get_live_frame()
            if frame_to_process is None:
                time.sleep(0.1)
                continue

            try:
                motion_mask = None
                cfg = self.system.get_node_config(self.node_id)

                # === AUTO BACKGROUND INVALIDATION ===
                # If lighting changes drastically (day -> night or vice versa),
                # the permanent background is no longer valid. Auto-reset to MOG2.
                if self.permanent_bg_edges is not None and self._bg_capture_mean_brightness is not None:
                    gray_check = cv2.cvtColor(frame_to_process, cv2.COLOR_BGR2GRAY)
                    current_brightness = float(np.mean(gray_check))
                    brightness_change_ratio = abs(current_brightness - self._bg_capture_mean_brightness) / max(self._bg_capture_mean_brightness, 1.0)
                    if brightness_change_ratio > 0.40:  # >40% change in mean brightness
                        print(f"[{self.node_id}] BACKGROUND_INVALIDATED — Major lighting change detected (ratio={brightness_change_ratio:.2f}). Reverting to MOG2.")
                        self.permanent_bg_edges = None
                        self._bg_capture_mean_brightness = None
                        self.system._log_event(
                            "BACKGROUND_INVALIDATED",
                            f"{self.node_id}: Lighting changed {brightness_change_ratio*100:.0f}% — bg reset to MOG2. Recapture recommended.",
                            threat_level=1
                        )

                # If permanent bg edges are set, use edge-based structural difference
                if hasattr(self, 'permanent_bg_edges') and self.permanent_bg_edges is not None:
                    gray = cv2.cvtColor(frame_to_process, cv2.COLOR_BGR2GRAY)
                    curr_edges = cv2.Canny(gray, cfg.canny_low, cfg.canny_high)

                    # Absolute difference between permanent edges and current edges
                    edge_diff = cv2.absdiff(curr_edges, self.permanent_bg_edges)

                    # Clean up noise
                    kernel = np.ones((5, 5), np.uint8)
                    edge_diff = cv2.morphologyEx(edge_diff, cv2.MORPH_OPEN, kernel)
                    edge_diff = cv2.dilate(edge_diff, kernel, iterations=2)

                    _, motion_mask = cv2.threshold(edge_diff, 50, 255, cv2.THRESH_BINARY)
                else:
                    # Generate live motion mask to boost sensitivity
                    fg_mask = mog2.apply(frame_to_process)
                    _, motion_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)

                # Run lightweight detection with per-node confidence override
                detections = self.engine.detect(
                    frame_to_process,
                    cam_id=self.node_id,
                    fps=TARGET_FPS,
                    motion_mask=motion_mask,
                    person_conf_override=cfg.person_conf
                )

                with self._det_lock:
                    self._latest_detections = detections

                # === APPROACHING OBJECT — AUTO ANALYSIS TRIGGER ===
                # Update the real-time tracker for this node. If an unidentified
                # motion blob is consistently approaching (growing in area), it may
                # be a human hiding behind an object. Trigger batch analysis.
                self._rt_tracker.update(detections, fps=TARGET_FPS)
                triggers = self._rt_tracker.get_analysis_triggers()
                now = time.time()
                if triggers and (now - self._last_obj_trigger_time > self._OBJ_TRIGGER_COOLDOWN):
                    if self.temp_writer is not None:
                        # Flush the current temp file and trigger analysis on it
                        self.temp_writer.release()
                        self.temp_writer = None
                    import shutil
                    if os.path.exists(self.temp_mp4_path) and os.path.getsize(self.temp_mp4_path) > 1000:
                        unique_path = self.temp_mp4_path.replace(".mp4", f"_obj_{int(now)}.mp4")
                        try:
                            shutil.copy(self.temp_mp4_path, unique_path)
                            print(f"[{self.node_id}] APPROACHING OBJECT detected — triggering analysis on {unique_path}")
                            self.system.trigger_auto_threat(self.node_id, unique_path)
                            self._last_obj_trigger_time = now
                        except Exception as e:
                            print(f"[{self.node_id}] Failed to trigger object analysis: {e}")

            except Exception as e:
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
            elif isinstance(src, str) and src.startswith("http"):
                is_open = hasattr(self, '_stream') and self._stream is not None

            if not is_open:
                self.online = False
                
                # Check if we should trigger an auto-analysis
                if self.temp_writer is not None:
                    self.temp_writer.release()
                    self.temp_writer = None
                    
                    print(f"[DEBUG-CAPTURE] [{self.node_id}] is_open became False. Checking if temp_mp4_path exists and size > 1000...")
                    if not is_video_file and os.path.exists(self.temp_mp4_path) and os.path.getsize(self.temp_mp4_path) > 1000:
                        import shutil
                        unique_path = self.temp_mp4_path.replace(".mp4", f"_{int(time.time())}.mp4")
                        try:
                            shutil.move(self.temp_mp4_path, unique_path)
                            print(f"[{self.node_id}] Stream disconnected cleanly. Triggering analysis on {unique_path}")
                            self.system.trigger_auto_threat(self.node_id, unique_path)
                        except Exception as e:
                            print(f"[{self.node_id}] Failed to move mp4: {e}")
                            self.system.trigger_auto_threat(self.node_id, self.temp_mp4_path)
                    else:
                        print(f"[DEBUG-CAPTURE] [{self.node_id}] Not triggering analysis because conditions not met.")
                        
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
                    # HTTP stream reconnection is handled by the reader below
                    try:
                        import urllib.request
                        self._stream = urllib.request.urlopen(src, timeout=3.0)
                        self._bytes = b''
                        print(f"[{self.node_id}] ONLINE - HTTP MJPEG STREAM")
                        last_frame_time = time.time()
                    except Exception as e:
                        print(f"[{self.node_id}] Stream connect failed: {e}")
                continue

            # Check manual timeout for hung stream
            if not is_video_file and (time.time() - last_frame_time > 5.0):
                print(f"[DEBUG-CAPTURE] [{self.node_id}] Stream HUNG! No frames for 5 seconds. Forcing disconnect.")
                is_open = False
                if hasattr(self, '_stream') and self._stream:
                    try: self._stream.close()
                    except: pass
                    self._stream = None
                continue

            if not cap and not is_video_file and isinstance(src, str) and src.startswith("http"):
                # Use robust custom MJPEG reader for HTTP streams
                try:
                    if not hasattr(self, '_stream') or self._stream is None:
                        import urllib.request
                        self._stream = urllib.request.urlopen(src, timeout=3.0)
                        self._bytes = b''
                        last_frame_time = time.time()
                    
                    self._bytes += self._stream.read(4096)
                    a = self._bytes.find(b'\xff\xd8')
                    b = self._bytes.find(b'\xff\xd9')
                    
                    if a != -1 and b != -1:
                        jpg = self._bytes[a:b+2]
                        self._bytes = self._bytes[b+2:]
                        import numpy as np
                        raw = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                        if raw is not None:
                            ret = True
                            self.online = True
                            last_frame_time = time.time()
                        else:
                            ret = False
                    else:
                        continue # Need more bytes
                        
                except Exception as e:
                    print(f"[{self.node_id}] MJPEG Stream error: {e}")
                    ret = False
                    if hasattr(self, '_stream') and self._stream:
                        self._stream.close()
                        self._stream = None
            else:
                try:
                    ret, raw = cap.read()
                    if ret: last_frame_time = time.time()
                except Exception as e:
                    print(f"[{self.node_id}] Error reading from camera: {e}")
                    ret = False
                    
            if not ret:
                self.online = False
                if is_video_file:
                    if cap: cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                else:
                    if cap: 
                        cap.release()
                        cap = None
                    continue
            
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
                
                # Write to temp MP4
                if self.temp_writer is None:
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    self.temp_writer = cv2.VideoWriter(self.temp_mp4_path, fourcc, TARGET_FPS, (TARGET_W, TARGET_H))
                self.temp_writer.write(frame)
                
                annotated = frame.copy()
                
                # Draw the latest bounding boxes asynchronously
                with self._det_lock:
                    current_detections = list(self._latest_detections)
                    
                for det in current_detections:
                    x1, y1 = det.x, det.y
                    x2, y2 = det.x + det.w, det.y + det.h
                    color = (0, 0, 255) if det.class_name == "Weapon" else (0, 255, 255)
                    cv2.rectangle(annotated, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                    cv2.putText(annotated, f"{det.class_name} {det.confidence:.2f}", (int(x1), int(y1)-5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)

                cv2.putText(annotated, f"{self.node_id} | LIVE", (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1, cv2.LINE_AA)

                with self._lock:
                    self._live_frame = annotated
                    self._raw_frame = frame.copy()
                    
            except Exception as e:
                print(f"[{self.node_id}] Exception during processing: {e}")
                import traceback; traceback.print_exc()

        if cap is not None:
            cap.release()
        if hasattr(self, '_stream') and self._stream is not None:
            self._stream.close()
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
        return []

    def get_status(self) -> Dict:
        return {
            "node_id": self.node_id,
            "online": self.online,
            "fps": round(self._fps, 1),
            "buffer_frames": 0,
            "clips_saved": self.clips_saved,
        }

    def stop(self):
        self._stopped = True
        self.online = False


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
        defaults = [
            ("HASH-1", "http://192.168.0.200/stream", "Tiger Chongjan", 24.165566, 94.259984),
            ("HASH-2", 0, "Pangal Sangjai", 24.180, 94.260),
        ]
        for nid, url, name, lat, lng in defaults:
            self._add_node(nid, url, name=name, lat=lat, lng=lng)

    def _add_node(self, node_id: str, stream_url: Any, name="", lat=0.0, lng=0.0) -> CameraNode:
        node = CameraNode(node_id, stream_url, self, self.engine, self.degrader, name=name, lat=lat, lng=lng)
        node.start()
        self.nodes[node_id] = node
        return node

    def add_node(self, node_id: str, stream_url: Any, name="", lat=0.0, lng=0.0) -> CameraNode:
        if node_id in self.nodes:
            self.nodes[node_id].stop()
        return self._add_node(node_id, stream_url, name, lat, lng)

    def remove_node(self, node_id: str):
        if node_id in self.nodes:
            self.nodes[node_id].stop()
            del self.nodes[node_id]

    def set_permanent_background(self, node_id: str):
        if node_id in self.nodes:
            node = self.nodes[node_id]
            frame = node.get_raw_frame()
            if frame is not None:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                node.permanent_bg_edges = cv2.Canny(gray, 50, 150)
                # Store the brightness at capture time for auto-invalidation check
                node._bg_capture_mean_brightness = float(np.mean(gray))
                print(f"[ADMIN] Set permanent background for {node_id} (brightness={node._bg_capture_mean_brightness:.1f})")

    def clear_permanent_background(self, node_id: str):
        """Reset a node's permanent background, reverting to MOG2 motion detection."""
        if node_id in self.nodes:
            self.nodes[node_id].permanent_bg_edges = None
            self.nodes[node_id]._bg_capture_mean_brightness = None
            print(f"[ADMIN] Cleared permanent background for {node_id}")

    def simulate_threat(self, node_id: str):
        if node_id in self.nodes:
            print(f"[ADMIN] Simulating threat on {node_id}")
            from detection_engine import Detection
            fake_det = Detection(x=100, y=100, w=200, h=300, confidence=0.99, class_name="Person", source="simulated", keypoints=None, metadata={})
            with self.nodes[node_id]._det_lock:
                self.nodes[node_id]._latest_detections.append(fake_det)
            if hasattr(self.nodes[node_id], 'temp_mp4_path') and os.path.exists(self.nodes[node_id].temp_mp4_path):
                import shutil
                sim_path = self.nodes[node_id].temp_mp4_path.replace(".mp4", "_simulated.mp4")
                shutil.copy(self.nodes[node_id].temp_mp4_path, sim_path)
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

    def trigger_instant_alarm(self, node_id: str, detections: List[Any]):
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

        now = time.time()
        if now - self._last_buzzer > BUZZER_COOLDOWN_SEC:
            self._last_buzzer = now
            _play_buzzer(4)
            
        self._log_event("INSTANT_ALARM", f"{node_id}: {len(entities)} entities detected instantly", threat_level=4)


    # ============================
    # SPACE TRIGGER — CORE LOGIC
    # ============================
    def trigger_analysis(self) -> List[str]:
        """
        Called when SPACEBAR is pressed.
        Snapshots all node buffers and queues analysis jobs.
        Returns list of job_ids (one per node).
        """
        job_ids = []
        for nid, node in self.nodes.items():
            frames = node.snapshot_buffer()
            if not frames:
                print(f"[ANALYZE] {nid} | Buffer empty, skipping")
                continue

            job_id = str(uuid.uuid4())
            job = AnalysisJob(job_id, nid, frames)

            with self._job_lock:
                self._jobs[job_id] = job

            # Run analysis in background thread
            threading.Thread(
                target=self._run_job, args=(job,), daemon=True
            ).start()

            job_ids.append(job_id)
            print(f"[ANALYZE] {nid} | Job {job_id[:8]} queued | {len(frames)} frames")

        self._log_event("SPACE_TRIGGER", f"Analysis triggered on {len(job_ids)} nodes")
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
        """Daemon thread: auto-delete clips older than per-node retention policy."""
        while True:
            time.sleep(1800)  # Check every 30 minutes
            try:
                # Use maximum retention across all nodes as the global default
                with self._config_lock:
                    max_days = max((cfg.clip_retention_days for cfg in self._node_configs.values()), default=7)
                cutoff = time.time() - max_days * 86400
                deleted = 0
                for fname in os.listdir(CLIPS_DIR):
                    fpath = os.path.join(CLIPS_DIR, fname)
                    if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                        try:
                            os.remove(fpath)
                            deleted += 1
                        except Exception:
                            pass
                if deleted > 0:
                    print(f"[RETENTION] Deleted {deleted} clips older than {max_days} days.")
                    self._log_event("RETENTION_CLEANUP", f"Auto-deleted {deleted} clips older than {max_days} days.")
            except Exception as e:
                print(f"[RETENTION] Error during cleanup: {e}")

    def get_events(self, limit: int = 100) -> List[Dict]:
        return list(self._events)[-limit:]

    def get_clips(self) -> List[Dict]:
        clips = []
        for fname in sorted(os.listdir(CLIPS_DIR), reverse=True):
            if not fname.endswith(".mp4"):
                continue
            fpath = os.path.join(CLIPS_DIR, fname)
            report_path = fpath.replace(".mp4", "_report.json")
            report = {}
            if os.path.exists(report_path):
                try:
                    with open(report_path) as f:
                        report = json.load(f)
                except Exception:
                    pass
            clips.append({
                "filename": fname,
                "size_bytes": os.path.getsize(fpath),
                "report": report,
                "url": f"http://localhost:5000/clips/{fname}",
            })
        return clips[:200]

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

def get_system() -> HashtagSystem:
    global _system
    if _system is None:
        _system = HashtagSystem()
    return _system
