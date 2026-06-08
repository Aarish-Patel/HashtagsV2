"""
validate_ov5647.py — Acceptance Test on Real OV5647 Imagery

Tests the detection pipeline against the actual OV5647 test image
(personOV.jpeg) which contains 2 men at the left edge at extreme range.

This image is NEVER used for training — it's the ground truth validation
that the system works on genuine field camera output.

Also tests against the empty scene images (Plane Pic.jpeg, Plane Pic 2.jpeg)
to verify false positive rate.
"""

import cv2
import numpy as np
import os
import sys
import time

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from detection_engine import DetectionEngine, Detection
from threat_classifier import EntityTracker, ThreatLevel, THREAT_CATEGORIES, THREAT_COLORS


# Paths to test images
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERSON_OV = os.path.join(BASE_DIR, "OV5647 pictures", "personOV.jpeg")
PLANE_PIC1 = os.path.join(BASE_DIR, "OV5647 pictures", "Plane Pic.jpeg")
PLANE_PIC2 = os.path.join(BASE_DIR, "OV5647 pictures", "Plane Pic 2.jpeg")


def run_detection_test(engine: DetectionEngine, image_path: str, test_name: str,
                        expect_persons: bool = True):
    """Run detection pipeline on a single test image and report results."""
    print(f"\n{'=' * 60}")
    print(f"  TEST: {test_name}")
    print(f"  Image: {os.path.basename(image_path)}")
    print(f"  Expected persons: {'YES' if expect_persons else 'NO (empty scene)'}")
    print(f"{'=' * 60}")

    if not os.path.exists(image_path):
        print(f"  [!] Image not found: {image_path}")
        return False

    frame = cv2.imread(image_path)
    if frame is None:
        print(f"  [!] Could not load image: {image_path}")
        return False

    print(f"  Image size: {frame.shape[1]}x{frame.shape[0]}")

    # Run detection
    t_start = time.time()
    detections = engine.detect(frame, cam_id=99, fps=5.0)
    t_elapsed = time.time() - t_start

    print(f"  Detection time: {t_elapsed:.3f}s")
    print(f"  Total detections: {len(detections)}")

    # Categorize results
    persons = [d for d in detections if d.class_name == "Person"]
    motion = [d for d in detections if d.class_name == "Motion"]
    concealed = [d for d in detections if d.class_name == "Concealed"]
    weapons = [d for d in detections if d.class_name == "Weapon"]

    print(f"\n  Persons:    {len(persons)}")
    print(f"  Motion:     {len(motion)}")
    print(f"  Concealed:  {len(concealed)}")
    print(f"  Weapons:    {len(weapons)}")

    # Detail each person detection
    for i, det in enumerate(persons):
        print(f"\n  [PERSON {i + 1}]")
        print(f"    BBox: ({det.x}, {det.y}) {det.w}x{det.h}")
        print(f"    Confidence: {det.confidence:.2%}")
        print(f"    Source: {det.source}")
        print(f"    Area: {det.area}px")
        if det.keypoints is not None:
            visible_kps = sum(1 for kp in det.keypoints if kp[2] > 0.3)
            print(f"    Keypoints: {visible_kps}/17 visible")

    # Draw results
    canvas = frame.copy()
    for det in detections:
        color = (0, 255, 0) if det.class_name == "Person" else (0, 180, 255)
        if det.class_name == "Weapon":
            color = (0, 0, 255)
        elif det.class_name == "Concealed":
            color = (0, 140, 255)

        cv2.rectangle(canvas, (det.x, det.y), (det.x + det.w, det.y + det.h), color, 2)
        label = f"{det.class_name} {det.confidence:.0%} ({det.source})"
        cv2.putText(canvas, label, (det.x, det.y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

    # Status text
    status = "PASS" if (expect_persons and len(persons) > 0) or (not expect_persons and len(persons) == 0) else "FAIL"
    status_color = (0, 255, 0) if status == "PASS" else (0, 0, 255)

    cv2.putText(canvas, f"TEST: {status} | Persons: {len(persons)} | Time: {t_elapsed:.2f}s",
                (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)
    cv2.putText(canvas, test_name, (10, canvas.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 200, 255), 1)

    # Save result
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "validation_results")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"result_{test_name.replace(' ', '_').lower()}.jpg")
    cv2.imwrite(output_path, canvas)
    print(f"\n  Result saved: {output_path}")

    # Show result
    cv2.imshow(f"Validation: {test_name}", canvas)
    print(f"\n  === RESULT: {status} ===")

    return status == "PASS"


def main():
    print("=" * 60)
    print("  HASHTAG V2 — OV5647 VALIDATION SUITE")
    print("=" * 60)

    # Initialize engine (first call will download models if needed)
    print("\n[*] Initializing detection engine...")
    engine = DetectionEngine(
        person_model_path="yolov8s.pt",
        pose_model_path="yolov8s-pose.pt",
        person_conf=0.15,
        pose_conf=0.20,
        use_sahi=True,
        sahi_slice_size=416,
        sahi_overlap=0.25,
    )

    results = {}

    # Test 1: personOV.jpeg — MUST detect at least 1 person
    results["PersonOV"] = run_detection_test(
        engine, PERSON_OV,
        "PersonOV Detection (2 men at left edge)",
        expect_persons=True
    )

    # Test 2: Plane Pic.jpeg — Should NOT detect persons (empty scene)
    results["EmptyScene1"] = run_detection_test(
        engine, PLANE_PIC1,
        "Empty Scene 1 (no persons expected)",
        expect_persons=False
    )

    # Test 3: Plane Pic 2.jpeg — Should NOT detect persons (empty scene)
    results["EmptyScene2"] = run_detection_test(
        engine, PLANE_PIC2,
        "Empty Scene 2 (no persons expected)",
        expect_persons=False
    )

    # === SUMMARY ===
    print("\n" + "=" * 60)
    print("  VALIDATION SUMMARY")
    print("=" * 60)
    all_pass = True
    for test_name, passed in results.items():
        status = "PASS ✓" if passed else "FAIL ✗"
        print(f"  {test_name:20s} : {status}")
        if not passed:
            all_pass = False

    overall = "ALL TESTS PASSED" if all_pass else "SOME TESTS FAILED"
    print(f"\n  Overall: {overall}")
    print("=" * 60)

    print("\nPress any key to close windows...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
