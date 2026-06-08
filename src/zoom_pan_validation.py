import cv2
import numpy as np
import os
import sys

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from detection_engine import DetectionEngine
from threat_classifier import EntityTracker

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERSON_OV = os.path.join(BASE_DIR, "OV5647 pictures", "personOV.jpeg")

def create_zoom_pan_video(image_path: str, output_path: str):
    if not os.path.exists(image_path):
        print(f"Error: {image_path} not found.")
        return

    img = cv2.imread(image_path)
    if img is None:
        print("Error: Could not read image.")
        return

    h, w = img.shape[:2]
    
    print("Initializing Detection Engine...")
    engine = DetectionEngine(
        person_model_path="models/heavy_person_detect.pt", # Use the heavier model
        pose_model_path="yolov8s-pose.pt",
        person_conf=0.15,
        use_sahi=True
    )
    
    tracker = EntityTracker(cam_id=101)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    # Use output dimensions of 800x640 to match expected system resolution
    out_w, out_h = 800, 640
    out = cv2.VideoWriter(output_path, fourcc, 10.0, (out_w, out_h))

    frames_to_generate = 100
    
    print(f"Generating {frames_to_generate} frames with simulated zoom & pan...")
    
    for i in range(frames_to_generate):
        # Calculate zoom factor (starts at 1.0, zooms in to 1.5, then back out)
        zoom = 1.0 + 0.5 * np.sin(i * np.pi / frames_to_generate)
        
        # Calculate pan offsets (pan right, then left)
        pan_x = 0.2 * w * np.sin(i * 2 * np.pi / frames_to_generate)
        pan_y = 0.1 * h * np.cos(i * 2 * np.pi / frames_to_generate)
        
        # Calculate new crop rectangle
        new_w = int(w / zoom)
        new_h = int(h / zoom)
        
        # Center of crop
        cx = w / 2 + pan_x
        cy = h / 2 + pan_y
        
        # Ensure bounds
        x1 = max(0, int(cx - new_w / 2))
        y1 = max(0, int(cy - new_h / 2))
        x2 = min(w, x1 + new_w)
        y2 = min(h, y1 + new_h)
        
        # Adjust if we hit bounds
        if x2 - x1 < new_w: x1 = x2 - new_w
        if y2 - y1 < new_h: y1 = y2 - new_h
        
        cropped = img[y1:y2, x1:x2]
        
        if cropped.size == 0:
            continue
            
        # Resize to standard
        frame = cv2.resize(cropped, (out_w, out_h))
        
        # Detect
        detections = engine.detect(frame, cam_id=101, fps=10.0)
        
        # Track
        active_tracks = tracker.update(detections, fps=10.0)
        
        # Draw annotations
        for tid, track in active_tracks.items():
            if track.stale_frames > 5:
                continue
            x, y, bw, bh = track.bboxes[-1]
            cv2.rectangle(frame, (x, y), (x+bw, y+bh), (0, 255, 0), 2)
            label = f"ID:{tid} {track.class_name}"
            cv2.putText(frame, label, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
        # Draw status text
        cv2.putText(frame, f"Frame {i}/{frames_to_generate} | Zoom {zoom:.2f}x", 
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                    
        out.write(frame)
        print(f"Processed frame {i}/{frames_to_generate}")
        
    out.release()
    print(f"Video saved to {output_path}")

if __name__ == "__main__":
    out_dir = os.path.join(BASE_DIR, "validation_results")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "heavy_validation.mp4")
    create_zoom_pan_video(PERSON_OV, out_file)
