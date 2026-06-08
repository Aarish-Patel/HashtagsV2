import os
import sys
import cv2
import time

# Add src folder to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from detection_engine import DetectionEngine

def main():
    print("=" * 60)
    # Correct path mapping for windows workspace
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    person_ov_path = os.path.join(base_dir, "OV5647 pictures", "personOV.jpeg")
    
    print(f"[*] Base directory: {base_dir}")
    print(f"[*] Testing image path: {person_ov_path}")
    
    if not os.path.exists(person_ov_path):
        print(f"[-] ERROR: Test image not found at {person_ov_path}")
        return
        
    print("[*] Initializing Detection Engine...")
    engine = DetectionEngine(
        person_model_path="yolov8s.pt",
        pose_model_path="yolov8s-pose.pt",
        person_conf=0.15,
        pose_conf=0.20,
        use_sahi=True,
    )
    
    print("[*] Loading image...")
    img = cv2.imread(person_ov_path)
    if img is None:
        print("[-] ERROR: Could not load image.")
        return
        
    print(f"[*] Image loaded. Resolution: {img.shape[1]}x{img.shape[0]}")
    print("[*] Running detection pipeline (YOLO + SAHI + Pose + Flow)...")
    
    t0 = time.time()
    detections = engine.detect(img, cam_id=99, fps=5.0)
    elapsed = time.time() - t0
    
    print(f"[+] Detection completed in {elapsed:.3f} seconds.")
    print(f"[+] Detected {len(detections)} entities:")
    
    for i, det in enumerate(detections):
        print(f"    [{i+1}] Class: {det.class_name:10s} | Conf: {det.confidence:.2%} | Source: {det.source:15s} | BBox: {det.bbox}")
        
    print("=" * 60)

if __name__ == "__main__":
    main()
