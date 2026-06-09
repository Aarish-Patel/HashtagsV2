"""
threat_classifier.py — Full Threat Taxonomy & Behavioral Analysis Engine

Implements the complete threat classification system with:
- Entity tracking with two-pass IoU+centroid matching
- Full behavioral analysis (speed, heading, approach, posture)
- Complete threat taxonomy (not just 5 levels)
- Group behavior detection (coordinated, flanking, infiltration)
- Posture classification from YOLO pose keypoints
- Load/object carrying detection
- Ghost zone persistence for concealment tracking
- Distance estimation from bounding box size
- Threat score 0-100 with category mapping

Entity persistence: tracks survive temporary occlusion and maintain
identity across frames for consistent threat assessment.
"""

import cv2
import numpy as np
import math
import time
from typing import List, Tuple, Optional, Dict, Any
from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum

from detection_engine import Detection, compute_iou
from gait_analyzer import GaitAnalyzer


# ================================================================
# THREAT TAXONOMY — Full classification system
# ================================================================

class ThreatLevel(IntEnum):
    """Numeric threat levels for sorting and comparison."""
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class ThreatCategory:
    """A specific threat classification with associated metadata."""
    name: str
    level: ThreatLevel
    description: str
    score_range: Tuple[int, int]  # Min-max threat score for this category

# Full threat taxonomy
THREAT_CATEGORIES = {
    "NO_THREAT":            ThreatCategory("No Threat / False Alarm",       ThreatLevel.NONE,     "No human activity detected",                           (0, 15)),
    "MOTION_CONTACT":       ThreatCategory("Unidentified Motion",           ThreatLevel.LOW,      "Motion detected, not confirmed human",                 (10, 25)),
    "PERSON_DETECTED":      ThreatCategory("Person Detected",               ThreatLevel.MEDIUM,   "Confirmed human presence, normal behavior",            (30, 45)),
    "SUSPICIOUS_ACTIVITY":  ThreatCategory("Suspicious Human Activity",     ThreatLevel.MEDIUM,   "Person exhibiting unusual behavior patterns",          (40, 55)),
    "LOITERING":            ThreatCategory("Loitering / Surveillance",      ThreatLevel.MEDIUM,   "Person stationary near perimeter for extended time",    (35, 50)),
    "CONCEALED_TARGET":     ThreatCategory("Concealed / Camouflaged",       ThreatLevel.HIGH,     "Target using concealment (ghillie, terrain cover)",     (55, 75)),
    "CRAWLING_APPROACH":    ThreatCategory("Low-Profile Movement",          ThreatLevel.HIGH,     "Crawling, prone, or crouching approach",                (55, 70)),
    "BORDER_CROSSING":      ThreatCategory("Potential Border Crossing",     ThreatLevel.HIGH,     "Individual moving across perimeter boundary",          (60, 80)),
    "LOAD_CARRYING":        ThreatCategory("Object / Load Carrying",        ThreatLevel.HIGH,     "Person carrying unusual objects or heavy load",         (50, 70)),
    "COORDINATED_GROUP":    ThreatCategory("Multiple Coordinated Individuals", ThreatLevel.HIGH,  "Multiple persons moving in coordinated pattern",       (65, 85)),
    "SMUGGLING_ACTIVITY":   ThreatCategory("Potential Smuggling Activity",  ThreatLevel.HIGH,     "Load carrying + border crossing indicators",           (70, 90)),
    "HOSTILE_APPROACH":     ThreatCategory("Potential Hostile Activity",     ThreatLevel.CRITICAL, "Running approach, erratic movement, or weapon",        (75, 95)),
    "WEAPON_DETECTED":      ThreatCategory("Weapon Detected",               ThreatLevel.CRITICAL, "Weapon identified in detection",                       (85, 100)),
    "PERIMETER_BREACH":     ThreatCategory("Perimeter Breach",              ThreatLevel.CRITICAL, "Tripwire or fence line breached",                      (80, 100)),
}

# Color coding for threat levels (BGR)
THREAT_COLORS = {
    ThreatLevel.NONE:     (0, 255, 0),       # Green
    ThreatLevel.LOW:      (0, 200, 255),      # Yellow/Cyan
    ThreatLevel.MEDIUM:   (0, 140, 255),      # Orange
    ThreatLevel.HIGH:     (0, 80, 255),       # Red-Orange
    ThreatLevel.CRITICAL: (0, 0, 255),        # Red
}

THREAT_LEVEL_LABELS = {
    ThreatLevel.NONE:     "SCANNING",
    ThreatLevel.LOW:      "LOW THREAT",
    ThreatLevel.MEDIUM:   "MED THREAT",
    ThreatLevel.HIGH:     "HIGH THREAT",
    ThreatLevel.CRITICAL: "CRITICAL",
}


# ================================================================
# POSTURE CLASSIFICATION from Pose Keypoints
# ================================================================

class PostureType(IntEnum):
    UNKNOWN = 0
    STANDING = 1
    WALKING = 2
    CROUCHING = 3
    CRAWLING = 4
    PRONE = 5
    CARRYING = 6
    ARMED = 7


def classify_posture(keypoints: Optional[np.ndarray]) -> PostureType:
    """
    Classify human posture from YOLOv8 pose keypoints.

    YOLO keypoint indices:
    0=Nose, 1=L_Eye, 2=R_Eye, 3=L_Ear, 4=R_Ear,
    5=L_Shoulder, 6=R_Shoulder, 7=L_Elbow, 8=R_Elbow,
    9=L_Wrist, 10=R_Wrist, 11=L_Hip, 12=R_Hip,
    13=L_Knee, 14=R_Knee, 15=L_Ankle, 16=R_Ankle

    Each keypoint is [x, y, confidence].
    """
    if keypoints is None or len(keypoints) < 17:
        return PostureType.UNKNOWN

    def kp_valid(idx):
        return keypoints[idx][2] > 0.3  # Confidence threshold

    def kp_pos(idx):
        return keypoints[idx][:2]

    # Check if we have enough keypoints for analysis
    visible = sum(1 for i in range(17) if kp_valid(i))
    if visible < 5:
        return PostureType.UNKNOWN

    # Key measurements
    shoulders_visible = kp_valid(5) and kp_valid(6)
    hips_visible = kp_valid(11) and kp_valid(12)
    ankles_visible = kp_valid(15) or kp_valid(16)

    if not (shoulders_visible or hips_visible):
        return PostureType.UNKNOWN

    # Body orientation: vertical extent vs horizontal extent
    valid_y = [keypoints[i][1] for i in range(17) if kp_valid(i)]
    valid_x = [keypoints[i][0] for i in range(17) if kp_valid(i)]

    if not valid_y or not valid_x:
        return PostureType.UNKNOWN

    body_height = max(valid_y) - min(valid_y)
    body_width = max(valid_x) - min(valid_x)

    if body_height < 10 and body_width < 10:
        return PostureType.UNKNOWN

    aspect = body_height / max(body_width, 1)

    # PRONE/CRAWLING: Body is more horizontal than vertical
    if aspect < 0.6 and body_width > body_height * 1.3:
        return PostureType.CRAWLING if body_height > 20 else PostureType.PRONE

    # CROUCHING: Shoulders and hips are close together vertically
    if shoulders_visible and hips_visible:
        shoulder_y = (kp_pos(5)[1] + kp_pos(6)[1]) / 2
        hip_y = (kp_pos(11)[1] + kp_pos(12)[1]) / 2
        torso_len = abs(hip_y - shoulder_y)

        if ankles_visible:
            ankle_y = kp_pos(15)[1] if kp_valid(15) else kp_pos(16)[1]
            total_height = abs(ankle_y - min(shoulder_y, hip_y))

            # If torso is short relative to total height, person is crouching
            if total_height > 0 and torso_len / total_height < 0.3:
                return PostureType.CROUCHING

    # CARRYING: Asymmetric arm positions or arms extended
    if kp_valid(9) and kp_valid(10):  # Both wrists visible
        l_wrist = kp_pos(9)
        r_wrist = kp_pos(10)

        if shoulders_visible:
            l_shoulder = kp_pos(5)
            r_shoulder = kp_pos(6)
            local_shoulder_y = (l_shoulder[1] + r_shoulder[1]) / 2

            # Arm extension: wrist far from shoulder
            l_arm_ext = math.hypot(l_wrist[0] - l_shoulder[0], l_wrist[1] - l_shoulder[1])
            r_arm_ext = math.hypot(r_wrist[0] - r_shoulder[0], r_wrist[1] - r_shoulder[1])

            # Both arms extended downward with load
            shoulder_width = math.hypot(l_shoulder[0] - r_shoulder[0], l_shoulder[1] - r_shoulder[1])
            if l_arm_ext > shoulder_width * 0.8 and r_arm_ext > shoulder_width * 0.8:
                # Check if wrists are below hips (carrying something heavy)
                if hips_visible:
                    hip_y = (kp_pos(11)[1] + kp_pos(12)[1]) / 2
                    if l_wrist[1] > hip_y and r_wrist[1] > hip_y:
                        return PostureType.CARRYING

            # ARMED: Both wrists are raised near or above shoulder level and close together (aiming posture)
            if l_wrist[1] <= local_shoulder_y + 30 and r_wrist[1] <= local_shoulder_y + 30:
                # Wrists are raised. Are they extended forward and together?
                wrist_dist = math.hypot(l_wrist[0] - r_wrist[0], l_wrist[1] - r_wrist[1])
                if wrist_dist < shoulder_width * 1.5:  # Hands relatively close = holding weapon
                    return PostureType.ARMED

    # STANDING (default upright posture)
    if aspect > 1.2:
        return PostureType.STANDING

    return PostureType.STANDING


# ================================================================
# TRACKED ENTITY — Persistent identity across frames
# ================================================================

class TrackedEntity:
    """
    Represents a single tracked target with full behavioral history.
    Maintains identity across frames and temporary occlusions.
    """

    # Camera calibration for distance estimation
    FOCAL_LENGTH = 500.0
    AVG_PERSON_HEIGHT_M = 1.7
    CRITICAL_DISTANCE_M = 8.0

    def __init__(self, entity_id: int, centroid: Tuple[int, int],
                 bbox: Tuple[int, int, int, int], class_name: str = "Person",
                 img_w: int = 800, img_h: int = 640):
        self.id = entity_id
        self.class_name = class_name

        # Temporal history
        self.history: deque = deque(maxlen=120)        # Position trail
        self.velocities: deque = deque(maxlen=120)     # Speed vectors
        self.bboxes: deque = deque(maxlen=120)         # Bounding box history
        self.area_history: deque = deque(maxlen=60)    # Size history (approach detection)
        self.posture_history: deque = deque(maxlen=30) # Posture classifications

        # Threat state
        self.threat_score: int = 0
        self.threat_category: str = "NO_THREAT"
        self.threat_level: ThreatLevel = ThreatLevel.NONE
        self.behavior: str = "DETECTED"

        # Tracking state
        self.stale_frames: int = 0
        self.confirmed_frames: int = 1
        self.first_seen: float = time.time()
        self.last_seen: float = time.time()
        self.distance_m: float = -1.0

        # Perimeter state
        self.tripwire_breached: bool = False
        self.tripwire_decay: int = 0
        self.tamper_frames: int = 0
        self.time_in_zone_sec: float = 0.0

        # Approaching object flag — set True when this motion blob is approaching
        # and should trigger a full batch analysis job on the backend
        self.triggers_analysis: bool = False

        # Posture
        self.current_posture: PostureType = PostureType.UNKNOWN
        self.keypoints: Optional[np.ndarray] = None
        
        # Biomechanics
        self.gait_analyzer = GaitAnalyzer(fps=5.0)

        # Initialize
        self.update(centroid, bbox, img_w=img_w, img_h=img_h)

    def calculate_distance(self, bbox_w: int, bbox_h: int) -> float:
        """Estimate distance using pinhole camera model."""
        effective_h = max(bbox_w, bbox_h) if bbox_w > bbox_h * 1.2 else bbox_h
        if effective_h < 5:
            return -1.0
        return round((self.AVG_PERSON_HEIGHT_M * self.FOCAL_LENGTH) / max(effective_h, 1), 1)

    def update(self, centroid: Tuple[int, int], bbox: Tuple[int, int, int, int],
               keypoints: Optional[np.ndarray] = None,
               fps: float = 5.0, img_w: int = 800, img_h: int = 640):
        """Update entity with new detection data from current frame."""
        self.last_seen = time.time()

        # Velocity
        if self.history:
            prev = self.history[-1]
            self.velocities.append((centroid[0] - prev[0], centroid[1] - prev[1]))

            # Tripwire check (60% down)
            tripwire_y = int(img_h * 0.6)
            if prev[1] < tripwire_y and centroid[1] >= tripwire_y:
                self.tripwire_breached = True
                self.tripwire_decay = 150

        self.history.append(centroid)

        # Smooth bounding box (EMA)
        if self.bboxes:
            alpha = 0.55
            prev_box = self.bboxes[-1]
            smoothed = tuple(int(alpha * c + (1 - alpha) * p) for c, p in zip(bbox, prev_box))
            self.bboxes.append(smoothed)
        else:
            self.bboxes.append(bbox)

        bx, by, bw, bh = self.bboxes[-1]
        self.area_history.append(bw * bh)

        # Keypoints / posture
        if keypoints is not None:
            self.keypoints = keypoints
            self.current_posture = classify_posture(keypoints)
            self.posture_history.append(self.current_posture)

        # Distance
        self.stale_frames = 0
        self.confirmed_frames += 1
        self.time_in_zone_sec = time.time() - self.first_seen

        if self.class_name == "Person":
            self.distance_m = self.calculate_distance(bw, bh)

        # Behavioral analysis
        self.analyze(fps, img_w, img_h)

    def analyze(self, fps: float = 5.0, img_w: int = 800, img_h: int = 640):
        """
        Full behavioral analysis producing threat score and category.
        """
        # === WEAPON — immediate critical ===
        if self.class_name == "Weapon":
            self.behavior = "WEAPON IDENTIFIED"
            self.threat_score = 90
            self.threat_category = "WEAPON_DETECTED"
            self.threat_level = ThreatLevel.CRITICAL
            return

        # === MOTION CONTACT — unconfirmed ===
        if self.class_name == "Motion":
            self._analyze_motion()
            return

        # === CONCEALED TARGET ===
        if self.class_name == "Concealed":
            self.behavior = "CONCEALED TARGET"
            self.threat_score = 65
            self.threat_category = "CONCEALED_TARGET"
            self.threat_level = ThreatLevel.HIGH
            return

        # === PERSON — full behavioral analysis ===
        self._analyze_person(fps, img_w, img_h)

    def _analyze_motion(self):
        """Analyze unconfirmed motion contacts."""
        self.behavior = "MOTION CONTACT"
        self.threat_score = 15
        self.threat_category = "MOTION_CONTACT"
        self.threat_level = ThreatLevel.LOW
        self.triggers_analysis = False

        # === APPROACHING OBJECT DETECTION ===
        # Per user directive: an unidentified object consistently growing in frame area
        # MUST be escalated to HIGH threat. A human may be hiding behind/under it
        # and using it as concealment while approaching the perimeter.
        # Confirmed humans are ALWAYS threats (MEDIUM+) regardless of movement.
        areas = list(self.area_history)
        if len(areas) >= 10:
            early = np.mean(areas[:3])
            late = np.mean(areas[-3:])
            growth_ratio = late / max(early, 1)

            if early > 100 and growth_ratio > 1.5:
                # Significant approach — escalate to HIGH, draw box, trigger analysis
                self.behavior = "APPROACHING OBJECT — POSSIBLE CONCEALMENT"
                self.threat_score = 65
                self.threat_category = "CONCEALED_TARGET"
                self.threat_level = ThreatLevel.HIGH
                self.triggers_analysis = True   # Backend will trigger batch analysis
            elif early > 100 and growth_ratio > 1.25:
                # Moderate approach — suspicious, escalate to MEDIUM
                self.behavior = "MOTION APPROACHING"
                self.threat_score = 35
                self.threat_category = "SUSPICIOUS_ACTIVITY"
                self.threat_level = ThreatLevel.MEDIUM

        # === BIOMECHANICAL GAIT ANALYSIS (Anti-Camouflage) ===
        # If it looks like a bush but walks like a human, it's a human.
        gait_data = self.gait_analyzer.analyze_kinematics(self.history, self.velocities)
        if gait_data["is_human_gait"]:
            self.behavior = f"CAMOUFLAGED HUMAN ({gait_data['gait_type']})"
            self.threat_score = max(self.threat_score, 75)
            self.threat_category = "CONCEALED_TARGET"
            self.threat_level = ThreatLevel.CRITICAL
            self.triggers_analysis = True

    def _analyze_person(self, fps: float, img_w: int, img_h: int):
        """Full person behavioral analysis with threat scoring."""
        fps_s = max(fps, 1.0)

        # Speed thresholds scaled to resolution and FPS
        scale = img_h / 480.0
        stand_max = (35.0 * scale) / fps_s
        patrol_min = (50.0 * scale) / fps_s
        run_min = (100.0 * scale) / fps_s
        min_move = (75.0 * scale) / fps_s
        fence_dist = 40.0 * scale

        # === BASE SCORE: Person confirmed ===
        score = 30  # Base presence score
        behavior = "SCANNING TARGET"
        category = "PERSON_DETECTED"

        if len(self.history) < 5:
            self.behavior = behavior
            self.threat_score = score
            self.threat_category = category
            self.threat_level = ThreatLevel.MEDIUM
            return

        # === SPEED ANALYSIS ===
        vels = list(self.velocities)
        speeds = [math.hypot(vx, vy) for vx, vy in vels]
        avg_speed = np.mean(speeds[-10:]) if len(speeds) >= 10 else np.mean(speeds)

        if avg_speed > run_min:
            behavior = "RUNNING"
            score += 15
            category = "HOSTILE_APPROACH"
        elif avg_speed > patrol_min:
            behavior = "PATROLLING"
            score += 10
            category = "SUSPICIOUS_ACTIVITY"
        elif avg_speed > stand_max:
            behavior = "MOVING"
            score += 5
        else:
            behavior = "STATIONARY"

        # === APPROACH DETECTION ===
        areas = list(self.area_history)
        if len(areas) >= 15:
            early = np.mean(areas[:5])
            late = np.mean(areas[-5:])
            if early > 100 and late > early * 1.3:
                behavior = "APPROACHING"
                score += 10
                if category not in ("HOSTILE_APPROACH",):
                    category = "BORDER_CROSSING"

        # === BIOMECHANICAL GAIT ANALYSIS ===
        gait_data = self.gait_analyzer.analyze_kinematics(self.history, self.velocities)
        if gait_data["is_human_gait"]:
            if "CRAWLING" in gait_data["gait_type"]:
                behavior = "TACTICAL CRAWL"
                score += 25
                category = "CRAWLING_APPROACH"
            
        # Tactical evasive bounding (up/down rapidly)
        if self.gait_analyzer.analyze_pose_rhythm(self.posture_history):
            behavior = "EVASIVE MANEUVERS"
            score += 20
            category = "HOSTILE_APPROACH"

        # === ERRATIC MOVEMENT ===
        if avg_speed > stand_max:
            headings = [
                math.degrees(math.atan2(vy, vx))
                for vx, vy in vels if math.hypot(vx, vy) > min_move
            ]
            if len(headings) >= 5:
                heading_std = np.std(headings[-10:]) if len(headings) >= 10 else np.std(headings)
                if heading_std > 60.0:
                    behavior = "ERRATIC MOVEMENT"
                    score += 15
                    category = "HOSTILE_APPROACH"

        # === POSTURE SCORING ===
        if self.current_posture == PostureType.CRAWLING or self.current_posture == PostureType.PRONE:
            score += 20
            behavior = "CRAWLING / PRONE"
            category = "CRAWLING_APPROACH"
        elif self.current_posture == PostureType.CROUCHING:
            score += 10
            if "CRAWLING" not in behavior:
                behavior = "CROUCHING"
            if category == "PERSON_DETECTED":
                category = "SUSPICIOUS_ACTIVITY"
        elif self.current_posture == PostureType.CARRYING:
            score += 15
            behavior = "CARRYING LOAD"
            category = "LOAD_CARRYING"
        elif self.current_posture == PostureType.ARMED:
            score += 35
            behavior = "ARMED POSTURE"
            category = "WEAPON_DETECTED"

        # === PROXIMITY ===
        if 0 < self.distance_m < self.CRITICAL_DISTANCE_M:
            score += 20
            behavior = f"PROXIMITY ({self.distance_m}m)"
            if category not in ("HOSTILE_APPROACH", "WEAPON_DETECTED"):
                category = "BORDER_CROSSING"
        elif 0 < self.distance_m < 15.0:
            score += 10

        # === LOITERING ===
        if self.time_in_zone_sec > 30 and avg_speed < stand_max:
            score += 5
            if category == "PERSON_DETECTED":
                behavior = "LOITERING"
                category = "LOITERING"

        # === FENCE TAMPERING ===
        x, y, w, h = self.bboxes[-1]
        near_edge = (x < fence_dist or y < fence_dist or
                     (x + w) > (img_w - fence_dist) or
                     (y + h) > (img_h - fence_dist))
        if near_edge and avg_speed < stand_max:
            self.tamper_frames += 1
        else:
            self.tamper_frames = max(0, self.tamper_frames - 1)

        if self.tamper_frames > 45:
            score += 20
            behavior = "FENCE TAMPERING"
            category = "PERIMETER_BREACH"

        # === TRIPWIRE BREACH ===
        if self.tripwire_breached:
            score += 20
            behavior = "TRIPWIRE BREACH"
            category = "PERIMETER_BREACH"
            self.tripwire_decay -= 1
            if self.tripwire_decay <= 0:
                self.tripwire_breached = False

        # === STALE CONTACT ===
        if self.stale_frames > 0:
            score = max(score - 10, 15)
            behavior = f"LOST CONTACT ({behavior})"

        # === FINAL ASSIGNMENT ===
        self.threat_score = min(100, max(0, score))
        self.behavior = behavior
        self.threat_category = category

        # Map score to level
        if self.threat_score >= 75:
            self.threat_level = ThreatLevel.CRITICAL
        elif self.threat_score >= 55:
            self.threat_level = ThreatLevel.HIGH
        elif self.threat_score >= 30:
            self.threat_level = ThreatLevel.MEDIUM
        elif self.threat_score >= 10:
            self.threat_level = ThreatLevel.LOW
        else:
            self.threat_level = ThreatLevel.NONE


# ================================================================
# ENTITY TRACKER — Multi-camera tracking with persistence
# ================================================================

class GhostZone:
    """Location where a person disappeared — monitors for re-emergence."""
    def __init__(self, bbox: Tuple[int, int, int, int], entity_id: int, ttl: int = 150):
        self.bbox = bbox
        self.entity_id = entity_id
        self.ttl = ttl
        self.created = time.time()

    @property
    def alive(self) -> bool:
        return self.ttl > 0

    def tick(self):
        self.ttl -= 1


class EntityTracker:
    """
    Manages all tracked entities for a single camera.
    Implements two-pass IoU+centroid matching from HashtagV1 with
    enhanced entity persistence and ghost zone tracking.
    """

    def __init__(self, cam_id: int, img_w: int = 800, img_h: int = 640):
        self.cam_id = cam_id
        self.img_w = img_w
        self.img_h = img_h
        self.tracks: Dict[int, TrackedEntity] = {}
        self.next_id = cam_id * 1000 + 1
        self.ghost_zones: List[GhostZone] = []
        self.concealed_alerts: List[GhostZone] = []
        self.camera_threat: ThreatLevel = ThreatLevel.NONE
        self.camera_threat_score: int = 0

        # Track purging thresholds
        self.max_stale_frames = 15
        self.track_purge_frames = 30
        self.ghost_zone_ttl = 150
        self.min_confirm_frames = 1

    def update(self, detections: List[Detection], fps: float = 5.0) -> Dict[int, TrackedEntity]:
        """
        Match new detections to existing tracks. Returns all active tracks.
        """
        matched_tracks = set()
        matched_dets = set()

        # === PASS 1: IoU Matching (handles slow/stationary targets) ===
        for i, det in enumerate(detections):
            best_id, best_iou = None, 0.25
            for tid, track in self.tracks.items():
                if tid in matched_tracks:
                    continue
                if track.class_name != det.class_name and det.class_name != "Concealed":
                    continue
                iou = compute_iou(det.bbox, track.bboxes[-1])
                if iou > best_iou:
                    best_iou, best_id = iou, tid

            if best_id is not None:
                self.tracks[best_id].update(
                    det.centroid, det.bbox, det.keypoints,
                    fps, self.img_w, self.img_h
                )
                # Upgrade class if detection is more specific
                if det.class_name == "Person" and self.tracks[best_id].class_name == "Motion":
                    self.tracks[best_id].class_name = "Person"
                matched_tracks.add(best_id)
                matched_dets.add(i)

        # === PASS 2: Centroid Matching (handles fast-moving targets) ===
        for i, det in enumerate(detections):
            if i in matched_dets:
                continue

            best_id, best_d = None, 120  # Max centroid distance
            for tid, track in self.tracks.items():
                if tid in matched_tracks:
                    continue
                if track.class_name != det.class_name and det.class_name != "Concealed":
                    continue
                d = math.hypot(det.cx - track.history[-1][0], det.cy - track.history[-1][1])
                if d < best_d:
                    best_d, best_id = d, tid

            if best_id is not None:
                self.tracks[best_id].update(
                    det.centroid, det.bbox, det.keypoints,
                    fps, self.img_w, self.img_h
                )
                if det.class_name == "Person" and self.tracks[best_id].class_name == "Motion":
                    self.tracks[best_id].class_name = "Person"
                matched_tracks.add(best_id)
            else:
                # Create new track
                entity = TrackedEntity(
                    self.next_id, det.centroid, det.bbox,
                    det.class_name, self.img_w, self.img_h
                )
                if det.keypoints is not None:
                    entity.keypoints = det.keypoints
                    entity.current_posture = classify_posture(det.keypoints)
                self.tracks[self.next_id] = entity
                matched_tracks.add(self.next_id)
                self.next_id += 1

        # === GROUP BEHAVIOR ANALYSIS ===
        self._analyze_group_behavior(fps)

        # === CLEANUP & GHOST ZONES ===
        to_del = []
        max_threat = ThreatLevel.NONE
        max_score = 0

        for tid, track in self.tracks.items():
            if tid not in matched_tracks:
                track.stale_frames += 1
                if track.stale_frames > self.track_purge_frames:
                    # Create ghost zone for disappeared persons
                    if track.class_name == "Person" and track.bboxes:
                        gx, gy, gw, gh = track.bboxes[-1]
                        pad = int(max(gw, gh) * 0.4)
                        ghost_bbox = (
                            max(0, gx - pad), max(0, gy - pad),
                            min(self.img_w - gx + pad, gw + 2 * pad),
                            min(self.img_h - gy + pad, gh + 2 * pad)
                        )
                        self.ghost_zones.append(GhostZone(ghost_bbox, tid, self.ghost_zone_ttl))
                    to_del.append(tid)
                    continue
            else:
                track.analyze(fps, self.img_w, self.img_h)

            if track.stale_frames < 10 and track.confirmed_frames >= self.min_confirm_frames:
                if track.threat_level > max_threat:
                    max_threat = track.threat_level
                max_score = max(max_score, track.threat_score)

        for tid in to_del:
            del self.tracks[tid]

        # === GHOST ZONE LIFECYCLE ===
        self.concealed_alerts = []
        alive_ghosts = []
        for gz in self.ghost_zones:
            gz.tick()
            if not gz.alive:
                continue
            # Check if a person re-appeared in the ghost zone
            person_returned = any(
                compute_iou(gz.bbox, t.bboxes[-1]) > 0.2
                for t in self.tracks.values() if t.class_name == "Person"
            )
            if person_returned:
                continue  # Person found, ghost resolved

            # Check if there's motion in the ghost zone (concealment alert)
            motion_in_zone = any(
                compute_iou(gz.bbox, t.bboxes[-1]) > 0.1
                for t in self.tracks.values() if t.class_name == "Motion"
            )
            if motion_in_zone:
                self.concealed_alerts.append(gz)
                max_threat = max(max_threat, ThreatLevel.MEDIUM)

            alive_ghosts.append(gz)

        self.ghost_zones = alive_ghosts
        self.camera_threat = max_threat
        self.camera_threat_score = max_score

        return self.tracks

    def _analyze_group_behavior(self, fps: float):
        """
        Detect coordinated multi-person behavior patterns.
        """
        persons = [t for t in self.tracks.values()
                    if t.class_name == "Person" and t.stale_frames < 5 and t.confirmed_frames >= 5]

        if len(persons) < 2:
            return

        # Calculate inter-person distances and movement coherence
        centroids = [t.history[-1] for t in persons]
        velocities = []
        for t in persons:
            if t.velocities:
                velocities.append(t.velocities[-1])
            else:
                velocities.append((0, 0))

        # Movement direction similarity (cosine similarity)
        if len(velocities) >= 2:
            headings = []
            for vx, vy in velocities:
                speed = math.hypot(vx, vy)
                if speed > 2:
                    headings.append(math.atan2(vy, vx))

            if len(headings) >= 2:
                # Check if all moving in same direction (coordinated)
                heading_std = np.std(headings) if len(headings) > 1 else 0
                heading_range = max(headings) - min(headings) if len(headings) > 1 else 0

                if heading_std < 0.5 and len(headings) >= 2:
                    # Same direction = coordinated movement
                    for t in persons:
                        if t.threat_score < 65:
                            t.threat_score = max(t.threat_score, 65)
                            t.threat_category = "COORDINATED_GROUP"
                            t.threat_level = ThreatLevel.HIGH
                            t.behavior = f"COORDINATED ({len(persons)} targets)"

                # Check for flanking pattern (diverging directions)
                elif heading_range > 2.0 and len(headings) >= 2:
                    for t in persons:
                        if t.threat_score < 70:
                            t.threat_score = max(t.threat_score, 70)
                            t.threat_category = "COORDINATED_GROUP"
                            t.threat_level = ThreatLevel.HIGH
                            t.behavior = f"FLANKING ({len(persons)} targets)"

        # Check for smuggling indicators: load carrying + border crossing
        for t in persons:
            if t.current_posture == PostureType.CARRYING and t.tripwire_breached:
                t.threat_score = max(t.threat_score, 75)
                t.threat_category = "SMUGGLING_ACTIVITY"
                t.threat_level = ThreatLevel.HIGH
                t.behavior = "SMUGGLING SUSPECT"

    def get_active_entities(self) -> List[Dict[str, Any]]:
        """Return serializable entity list for API/logging."""
        entities = []
        for tid, track in self.tracks.items():
            if track.stale_frames > self.max_stale_frames:
                continue
            if track.confirmed_frames < self.min_confirm_frames:
                continue

            cat_info = THREAT_CATEGORIES.get(track.threat_category, THREAT_CATEGORIES["NO_THREAT"])
            entities.append({
                "id": tid,
                "camera": f"NODE-{self.cam_id}",
                "class": track.class_name,
                "behavior": track.behavior,
                "threat_level": int(track.threat_level),
                "threat_score": track.threat_score,
                "threat_category": track.threat_category,
                "threat_description": cat_info.description,
                "distance_m": track.distance_m,
                "posture": track.current_posture.name if track.current_posture else "UNKNOWN",
                "time_in_zone": round(track.time_in_zone_sec, 1),
                "bbox": list(track.bboxes[-1]) if track.bboxes else [0, 0, 0, 0],
                "triggers_analysis": getattr(track, 'triggers_analysis', False),
            })
        return entities

    def get_analysis_triggers(self) -> List[tuple]:
        """
        Returns list of (entity_id, bbox) for any tracked entity that has
        triggers_analysis=True. Used by CameraNode._inference_loop() to
        auto-trigger a batch analysis job when an approaching object is detected.

        Per user directive: an approaching unidentified object (concealment threat)
        triggers the same batch analysis pipeline as a confirmed human detection.
        """
        triggers = []
        for tid, track in self.tracks.items():
            if (
                getattr(track, 'triggers_analysis', False)
                and track.stale_frames < 5
                and track.confirmed_frames >= 3  # Require at least 3 frames before triggering
                and track.threat_level >= ThreatLevel.HIGH
            ):
                bbox = list(track.bboxes[-1]) if track.bboxes else None
                if bbox:
                    triggers.append((tid, bbox))
                    # Reset flag so we don't trigger repeatedly
                    track.triggers_analysis = False
        return triggers
