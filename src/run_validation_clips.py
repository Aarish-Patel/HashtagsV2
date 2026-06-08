import os
import sys
import cv2
import time
from typing import List
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from detection_engine import DetectionEngine
from hashtag_v2_backend import BatchAnalyzer, AnalysisJob

CLIPS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Clips")

def main():
    print("==================================================")
    print("  HASHTAG V2 — CLIP VALIDATION SUITE")
    print("==================================================")

    engine = DetectionEngine(
        person_model_path="yolov8s.pt",
        pose_model_path="yolov8s-pose.pt",
        person_conf=0.20,
        device=None
    )
    analyzer = BatchAnalyzer(engine)

    mp4_files = [f for f in os.listdir(CLIPS_DIR) if f.endswith(".mp4")]
    if not mp4_files:
        print("No clips found to validate.")
        return

    pass_count = 0
    fail_count = 0

    for i, fname in enumerate(mp4_files):
        fpath = os.path.join(CLIPS_DIR, fname)
        cap = cv2.VideoCapture(fpath)
        frames = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
        cap.release()

        job = AnalysisJob(f"val_{i}", f"NODE-VAL", frames)
        
        # Analyze using our corrected logic
        start_time = time.time()
        analyzer.analyze(job)
        end_time = time.time()

        proc_time = end_time - start_time
        fps = len(frames) / proc_time if proc_time > 0 else 0

        if job.threat_detected:
            print(f"[PASS] {fname} - Threat detected! (Max Level: {job.max_threat_level}, Entities: {len(job.entities)})")
            pass_count += 1
        else:
            print(f"[FAIL] {fname} - SECTOR CLEAR (Threat missed!)")
            fail_count += 1
            
        print(f"       -> Processing Time: {proc_time:.2f}s | FPS: {fps:.2f} | Frames: {len(frames)}")

    print("==================================================")
    print(f"  VALIDATION COMPLETE")
    print(f"  PASSED: {pass_count}")
    print(f"  FAILED: {fail_count}")
    print("==================================================")

if __name__ == "__main__":
    main()
