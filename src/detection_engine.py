"""
detection_engine.py — Pure YOLOv8 Detection Pipeline (Production v4)

DESIGN PHILOSOPHY:
==================
Previous versions used 5 detection stages (YOLO + SAHI + Pose + MOG2 Motion + Concealment).
These caused cascading false positives in jungle/border OV5647 imagery.

THIS VERSION uses only 2 detection stages:
  Stage 1: YOLOv8x Person Detection (conf >= 0.35 default, tunable per-node)
  Stage 2: YOLO COCO weapons detection (knife/scissors), filtered to overlap with a person.

Stage 3: Hierarchical NMS (merge overlapping boxes, absorb contained smaller boxes).

NOTE: Pose skeleton verification was explicitly removed by the operator. The custom
YOLOv8x model (Occlusion_Camouflage_V1) is robust enough without it.
Size limits are NOT implemented — people can be far away and have small bounding boxes.

PER-NODE TUNING:
================
Each camera node has its own YOLO confidence and Canny thresholds (stored in node_configs.json).
The detect() method accepts an optional person_conf_override to support this without
changing the global engine state (thread-safe, no lock needed for reads).

Author: HashtagV2 System — Production Military-Grade Iteration
"""

import cv2
import numpy as np
import math
import time
import os
from typing import List, Tuple, Optional, Dict, Any
from collections import deque
from dataclasses import dataclass, field


# YOLO models loaded lazily
_yolo_person_model = None

import threading
_model_lock = threading.Lock()

def _get_person_model(model_path: str = None, device: str = "cuda:0"):
    global _yolo_person_model
    with _model_lock:
        if _yolo_person_model is None:
            from ultralytics import YOLO
            base_path = model_path or "yolov8x.pt"
            
            # --- Model Optimization Hunt ---
            # Suggestion #2: TensorRT / ONNX Optimization
            # Try to load the fastest available format in order of priority:
            # 1. TensorRT (.engine)
            # 2. ONNX (.onnx)
            # 3. PyTorch native (.pt)
            
            path_no_ext = os.path.splitext(base_path)[0]
            engine_path = f"{path_no_ext}.engine"
            onnx_path = f"{path_no_ext}.onnx"
            
            if os.path.exists(engine_path):
                load_path = engine_path
                print(f"[OPTIMIZATION] TensorRT engine found! Using {load_path}")
            elif os.path.exists(onnx_path):
                load_path = onnx_path
                print(f"[OPTIMIZATION] ONNX model found! Using {load_path}")
            else:
                load_path = base_path
                print(f"[OPTIMIZATION] No TensorRT/ONNX found. Falling back to native PyTorch {load_path}")

            print(f"Loading YOLOv8 person model from {load_path} on device={device}...")
            _yolo_person_model = YOLO(load_path)
            
            # For ONNX/TensorRT, passing device ensures data stays on GPU
            _yolo_person_model.to(device)
    return _yolo_person_model



@dataclass
class Detection:
    """A single confirmed human detection after both pipeline stages."""
    x: int
    y: int
    w: int
    h: int
    confidence: float
    class_name: str          # "Person", "Weapon"
    source: str              # "yolo_verified", "yolo_partial", "weapon"
    keypoints: Optional[np.ndarray] = None    # 17x3 YOLO pose keypoints
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def cx(self) -> int:
        return self.x + self.w // 2

    @property
    def cy(self) -> int:
        return self.y + self.h // 2

    @property
    def centroid(self) -> Tuple[int, int]:
        return (self.cx, self.cy)

    @property
    def area(self) -> int:
        return self.w * self.h

    @property
    def bbox(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.w, self.h)


def compute_iou(box_a: Tuple, box_b: Tuple) -> float:
    """IoU between two (x, y, w, h) boxes."""
    ax1, ay1, aw, ah = box_a
    bx1, by1, bw, bh = box_b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    union = aw * ah + bw * bh - inter
    return inter / max(union, 1)


def compute_containment(box_a: Tuple, box_b: Tuple) -> float:
    """Fraction of box_a that is contained within box_b."""
    ax1, ay1, aw, ah = box_a
    bx1, by1, bw, bh = box_b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    area_a = max(aw * ah, 1)
    return inter / area_a


def hierarchical_nms(detections: List[Detection],
                     iou_thresh: float = 0.40,
                     containment_thresh: float = 0.70) -> List[Detection]:
    """
    Hierarchical NMS with containment merging.
    If a smaller box is >70% contained within a larger box, it is absorbed.
    This guarantees ONE box per entity, eliminating the multi-box problem.
    """
    if not detections:
        return []

    # Sort by: Person > Weapon, then by confidence descending
    priority_order = {"Person": 1, "Weapon": 0}
    sorted_dets = sorted(detections,
                         key=lambda d: (priority_order.get(d.class_name, 0), d.confidence),
                         reverse=True)

    keep = []
    for det in sorted_dets:
        suppress = False
        for k in keep:
            iou = compute_iou(det.bbox, k.bbox)
            # Containment: is 'det' mostly inside 'k'?
            containment = compute_containment(det.bbox, k.bbox)

            if iou > iou_thresh or containment > containment_thresh:
                suppress = True
                # Absorb keypoints into the dominant box if missing
                if k.keypoints is None and det.keypoints is not None:
                    k.keypoints = det.keypoints
                break

        if not suppress:
            keep.append(det)

    return keep





# ================================================================
# TEMPORAL WINDOW — 30-second rolling analysis per camera
# ================================================================

class TemporalRegion:
    """
    Tracks a spatial region that had human detections over time.
    Used to detect approach vectors — someone moving consistently
    toward the camera from a concealed position.
    """
    def __init__(self, bbox: Tuple, entity_id: int, timestamp: float):
        self.entity_id = entity_id
        self.centroid_history: deque = deque(maxlen=150)  # 30s at 5fps
        self.bbox_history: deque = deque(maxlen=150)
        self.first_seen = timestamp
        self.last_seen = timestamp
        self.approach_score = 0.0  # 0-1 how strongly it's approaching
        self.is_suspicious = False
        self.add_observation(bbox, timestamp)

    def add_observation(self, bbox: Tuple, timestamp: float):
        cx = bbox[0] + bbox[2] // 2
        cy = bbox[1] + bbox[3] // 2
        self.centroid_history.append((cx, cy, timestamp))
        self.bbox_history.append(bbox)
        self.last_seen = timestamp

    def analyze_approach(self, img_w: int, img_h: int) -> Dict[str, Any]:
        """
        Analyzes if the trajectory is a consistent approach vector.

        Key insight: A real intruder approaching the camera will:
          - Have growing bounding box size (getting larger = coming closer)
          - Have a consistent directional heading (not oscillating like a leaf)
          - Maintain this pattern for multiple seconds

        A random object (leaf, branch, shadow) will:
          - Have oscillating centroid (no net direction)
          - Have stable or random size changes
          - Show no consistent approach over 5+ seconds
        """
        if len(self.centroid_history) < 10:
            return {"is_approaching": False, "approach_score": 0.0}

        pts = list(self.centroid_history)
        if len(pts) < 10:
            return {"is_approaching": False, "approach_score": 0.0}

        # 1. Net displacement over window
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        net_dx = xs[-1] - xs[0]
        net_dy = ys[-1] - ys[0]
        net_dist = math.hypot(net_dx, net_dy)

        # 2. Total path length (including oscillations)
        total_path = sum(
            math.hypot(xs[i+1]-xs[i], ys[i+1]-ys[i])
            for i in range(len(xs)-1)
        )
        if total_path < 5:
            return {"is_approaching": False, "approach_score": 0.0}

        # 3. Linearity ratio: net_distance / total_path
        # A consistent approach has ratio close to 1.0
        # A leaf oscillating has ratio close to 0.0
        linearity = net_dist / max(total_path, 1)

        # 4. Box size growth (approaching = getting bigger)
        boxes = list(self.bbox_history)
        early_area = np.mean([b[2]*b[3] for b in boxes[:5]])
        late_area = np.mean([b[2]*b[3] for b in boxes[-5:]])
        size_growth = (late_area / max(early_area, 1)) - 1.0  # positive = growing

        # 5. Approach score combines linearity + size growth
        approach_score = min(1.0, linearity * 0.6 + max(0, size_growth) * 0.4)

        # A trajectory is suspicious if:
        # - Moving in a consistent direction (linearity > 0.5)
        # - AND getting larger (approaching) OR has moved significantly
        is_approaching = (linearity > 0.5 and
                          (size_growth > 0.10 or net_dist > img_w * 0.05))

        return {
            "is_approaching": is_approaching,
            "approach_score": round(approach_score, 2),
            "linearity": round(linearity, 2),
            "size_growth": round(size_growth, 2),
            "net_dist_px": round(net_dist, 1),
        }


class TemporalWindowAnalyzer:
    """
    Maintains a 30-second rolling analysis window per camera.

    Each human detection is tracked across frames. After enough history
    is accumulated, the trajectory is analyzed to determine if the entity
    is on an approach vector (suspicious) or just passing through.

    KEY RULE: Only human-verified detections get entered into this analyzer.
    Random objects never get in because they never pass the YOLO+Pose gate.
    """

    def __init__(self, window_seconds: float = 30.0, fps: float = 5.0):
        self.window_seconds = window_seconds
        self.fps = fps
        self.regions: Dict[int, TemporalRegion] = {}  # entity_id -> region

    def update(self, detections: List[Detection], tracked_ids: Dict[int, int],
               img_w: int, img_h: int) -> Dict[int, Dict]:
        """
        Update the temporal window with new detections.
        tracked_ids maps detection index -> entity_id from the tracker.
        Returns per-entity approach analysis results.
        """
        now = time.time()
        results = {}

        for i, det in enumerate(detections):
            entity_id = tracked_ids.get(i, -1)
            if entity_id < 0 or det.class_name != "Person":
                continue

            if entity_id not in self.regions:
                self.regions[entity_id] = TemporalRegion(det.bbox, entity_id, now)
            else:
                self.regions[entity_id].add_observation(det.bbox, now)

            analysis = self.regions[entity_id].analyze_approach(img_w, img_h)
            self.regions[entity_id].approach_score = analysis["approach_score"]
            self.regions[entity_id].is_suspicious = analysis["is_approaching"]
            results[entity_id] = analysis

        # Prune expired regions (not seen in last 2x window duration)
        cutoff = now - self.window_seconds * 2
        expired = [eid for eid, r in self.regions.items() if r.last_seen < cutoff]
        for eid in expired:
            del self.regions[eid]

        return results

    def get_approach_score(self, entity_id: int) -> float:
        if entity_id in self.regions:
            return self.regions[entity_id].approach_score
        return 0.0

    def is_suspicious(self, entity_id: int) -> bool:
        if entity_id in self.regions:
            return self.regions[entity_id].is_suspicious
        return False


# ================================================================
# MAIN DETECTION ENGINE
# ================================================================

class DetectionEngine:
    """
    Military-Grade 2-Stage Detection Pipeline.

    Stage 1: YOLOv8x Person Detection
      - conf >= 0.35 (eliminates phones, pillars, tree stumps)
      - Full-frame inference only (no SAHI slicing — causes duplicates)
      - COCO weapon classes as bonus detection (knife=43, sports equipment)

    Stage 2: Pose Skeleton Verification
      - For each candidate detection, run pose estimation
      - If >= 5 keypoints confirmed: "Person (Verified)" — highest confidence
      - If 2-4 keypoints: "Person (Partial)" — likely occluded, still accept
      - If 0-1 keypoints: reject IF low confidence (<0.50), keep if high confidence

    Stage 3: Hierarchical NMS
      - Merge overlapping boxes
      - Absorb contained smaller boxes into larger parent
      - Result: exactly 1 box per entity

    Per-camera temporal window analysis runs separately in the tracker.
    """

    # YOLO COCO class indices for weapon detection (no dedicated model needed)
    WEAPON_CLASSES = {43: "Knife", 76: "Scissors"}

    def __init__(
        self,
        person_model_path: str = "yolov8s.pt",
        device: Optional[str] = None,
        person_conf: float = 0.10,    # Lowered to detect partial bodies/crawling
        weapon_conf: float = 0.40,
        img_size: int = 640,          # Standard YOLOv8 resolution
    ):
        import torch
        self.device = device if device else ("cuda:0" if torch.cuda.is_available() else "cpu")
        self.person_conf = person_conf
        self.weapon_conf = weapon_conf
        self.person_model_path = person_model_path
        self.img_size = img_size

        # Models loaded lazily on first call
        self._person_model = None
        self._inference_lock = threading.Lock()
        
        # Fallback for extreme close-ups
        import cv2
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

        print(f"[ENGINE] DetectionEngine v3 initialized. Device={self.device}, "
              f"PersonConf={person_conf}, ImgSize={img_size}")

    def _ensure_models(self):
        if self._person_model is None:
            self._person_model = _get_person_model(self.person_model_path, self.device)

        if not hasattr(self, 'last_boxes'):
            self.last_boxes = {}

    def detect(self, frame: np.ndarray, cam_id: int = 0,
               fps: float = 5.0, active_boxes: List[Tuple] = None,
               motion_mask: np.ndarray = None,
               person_conf_override: Optional[float] = None) -> List[Detection]:
        """
        Run the 2-stage detection pipeline on a single frame.

        Args:
            frame:                Input BGR frame from camera.
            cam_id:               Camera identifier (for last_boxes tracking).
            fps:                  Frame rate (informational).
            active_boxes:         Previously tracked boxes (for continuity).
            motion_mask:          Optional MOG2/Canny motion mask.
            person_conf_override: Per-node confidence threshold override.
                                  If None, uses self.person_conf (global default).
                                  This allows per-camera tuning without lock contention.

        Returns:
            Deduplicated list of confirmed Person + Weapon detections.
        """
        self._ensure_models()
        h, w = frame.shape[:2]
        conf = person_conf_override if person_conf_override is not None else self.person_conf

        with self._inference_lock:
            # === STAGE 1: YOLO Person Detection ===
            if active_boxes is None:
                active_boxes = self.last_boxes.get(cam_id, [])

            verified = self._detect_persons(frame, active_boxes, motion_mask, conf)
            if not verified:
                self.last_boxes[cam_id] = []
                return []

            # === STAGE 2: Weapon Detection ===
            weapon_dets = self._detect_weapons(frame)

            # Filter false positive weapons: must overlap with a verified person
            valid_weapons = []
            for wd in weapon_dets:
                for pd in verified:
                    if pd.class_name == "Person":
                        if compute_iou(wd.bbox, pd.bbox) > 0 or compute_containment(wd.bbox, pd.bbox) > 0 or compute_containment(pd.bbox, wd.bbox) > 0:
                            valid_weapons.append(wd)
                            break

            verified.extend(valid_weapons)

            # === STAGE 3: Hierarchical NMS — 1 box per entity ===
            final = hierarchical_nms(verified, iou_thresh=0.25, containment_thresh=0.40)

            self.last_boxes[cam_id] = [d.bbox for d in final]
            return final

    def _detect_persons(self, frame: np.ndarray, active_boxes: List[Tuple] = None,
                        motion_mask: np.ndarray = None,
                        conf_override: Optional[float] = None) -> List[Detection]:
        """
        Stage 1: YOLOv8x full-frame person detection.
        conf_override allows per-node tuning without changing engine global state.
        """
        conf = conf_override if conf_override is not None else self.person_conf
        
        import cv2
        # Grayscale preprocessing for NoIR cameras (Pink tint fix)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_for_inference = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        results = self._person_model(
            frame_for_inference,
            classes=[0, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
            conf=conf,
            device=self.device,
            verbose=False,
            imgsz=self.img_size,
            half=(self.device != "cpu")
        )

        verified = []
        frame_h, frame_w = frame.shape[:2]
        
        COCO_CLASSES = {
            0: "Person", 14: "Bird", 15: "Cat", 16: "Dog", 17: "Horse", 
            18: "Sheep", 19: "Cow", 20: "Elephant", 21: "Bear", 22: "Zebra", 23: "Giraffe"
        }

        for b in results[0].boxes.data.cpu().numpy():
            x1, y1, x2, y2, conf_val, cls_id = b[:6]
            bbox = (int(x1), int(y1), int(x2-x1), int(y2-y1))
            cls_name = COCO_CLASSES.get(int(cls_id), "Animal")
            
            is_tracked = False
            if active_boxes:
                for ab in active_boxes:
                    if compute_iou(bbox, ab) > 0.05 or compute_containment(bbox, ab) > 0.1 or compute_containment(ab, bbox) > 0.1:
                        is_tracked = True
                        break

            has_motion = False
            if motion_mask is not None:
                mask_roi = motion_mask[int(y1):int(y2), int(x1):int(x2)]
                if mask_roi.size > 0 and cv2.countNonZero(mask_roi) > (mask_roi.size * 0.01):
                    has_motion = True

            source = "yolo_verified"
            if is_tracked: source = "yolo_tracked"
            elif has_motion: source = "yolo_motion"

            verified.append(Detection(
                x=bbox[0], y=bbox[1], w=bbox[2], h=bbox[3],
                confidence=float(conf_val),
                class_name=cls_name,
                source=source,
                keypoints=None,
                metadata={}
            ))

        # --- FALLBACK: Extreme Close-Up Face Detection ---
        # YOLOv8 struggles when the frame is 90% face/head.
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
            for (x, y, w, h) in faces:
                # Expand the box slightly downward to cover shoulders
                bbox = (x, y, w, int(h * 1.5))
                
                is_duplicate = False
                for v in verified:
                    if compute_iou(bbox, v.bbox) > 0.1 or compute_containment(bbox, v.bbox) > 0.5:
                        is_duplicate = True
                        break
                        
                if not is_duplicate:
                    verified.append(Detection(
                        x=bbox[0], y=bbox[1], w=bbox[2], h=bbox[3],
                        confidence=0.85,
                        class_name="Person",
                        source="face_fallback",
                        keypoints=None,
                        metadata={}
                    ))
        except Exception as e:
            pass

        return verified

    def _detect_weapons(self, frame: np.ndarray) -> List[Detection]:
        """
        Detect weapons using YOLO COCO built-in classes.
        Classes: 43=knife, 76=scissors (as blade proxy).
        """
        try:
            results = self._person_model(
                frame,
                classes=list(self.WEAPON_CLASSES.keys()),
                conf=self.weapon_conf,
                device=self.device,
                verbose=False,
                imgsz=self.img_size,
                half=(self.device != "cpu")
            )
            dets = []
            for b in results[0].boxes.data.cpu().numpy():
                x1, y1, x2, y2, conf, cls_id = b[:6]
                cls_name = self.WEAPON_CLASSES.get(int(cls_id), "Weapon")
                dets.append(Detection(
                    x=int(x1), y=int(y1),
                    w=int(x2-x1), h=int(y2-y1),
                    confidence=float(conf),
                    class_name="Weapon",
                    source="yolo_coco",
                    metadata={"weapon_class": cls_name}
                ))
            return dets
        except Exception:
            return []
