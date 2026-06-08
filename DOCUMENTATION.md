# HashtagV2 Documentation

Welcome to the definitive guide for **HashtagV2**, a military-grade multi-camera border surveillance and human detection system.

This documentation serves as the central reference point for understanding the system architecture, how the AI operates under the hood, how to tweak parameters, and how to run advanced model retraining pipelines to ensure continuous high reliability across any terrain.

---

## 1. System Architecture & Operational Paradigm

HashtagV2 uses a **Hybrid Standby-Batch Analysis Architecture** designed to completely eliminate false positives while guaranteeing that no human approaches are missed.

- **Standby Mode (Deep Sleep)**: The ESP32 camera nodes are normally in **deep sleep** to conserve power. There is **NO** continuous streaming to the base station during standby.
- **Trigger Event (Radar Wake-up)**: When the onboard radar detects movement, the ESP32 wakes up and immediately begins capturing a 30-second video clip.
- **Streaming & Analysis**: The node sends this 30-second clip to the base station. The base station streams this incoming clip to the GUI while simultaneously running the Batch Analyzer (YOLOv8 + Pose) on the frames.
- **Batch Analysis**: The backend iterates over the captured 30-second clip and runs a highly-accurate 2-stage inference pipeline (YOLOv8 + Pose). The analysis runs temporally—meaning it identifies trajectory, behavior, and approach vectors across multiple frames. If a threat is confirmed (e.g., person appears in >= 2 frames with approach behavior), an alarm is triggered and an annotated video clip is saved.

---

## 2. File Index & Responsibilities

### Core Backend Services
- **`hashtag_v2_backend.py`**: The main system orchestrator. Manages `CameraNode` buffers, triggers `BatchAnalyzer` jobs, handles video stream reconnection, and manages the YOLO engine instantiation. **Edit this to change the active models, add new hardcoded camera IPs, or change batch lengths.**
- **`api_server.py`**: The Flask HTTP web server. Exposes the `/api/analyze` trigger, serves video feeds, and pushes system statuses to the frontend GUI. 

### Machine Learning Pipeline
- **`detection_engine.py`**: The 2-stage ML pipeline. 
  - **Stage 1**: Detects humans using YOLOv8 bounding boxes.
  - **Stage 2**: Verifies humans using YOLO-Pose keypoints (skeleton) to reject false positives like swaying trees or shadows.
- **`threat_classifier.py`**: Tracks entities across multiple frames using ID matching (IoU + Centroid proximity). Analyzes behaviors (e.g., crawling, armed posture, flanking) and calculates a Threat Score (0 to 100).
- **`gait_analyzer.py`**: Biomechanical kinematics. Attempts to identify human movement patterns even when the subject is camouflaged.

### Tuning & Simulation
- **`augmentation_pipeline.py` & `ov5647_simulator.py`**: Applies severe digital degradation (chromatic aberration, sensor noise, low contrast) to clean training images to simulate the exact characteristics of the real-world OV5647 sensors.
- **`dataset_manager.py`**: Processes and pre-degrades training datasets so they can be fed into YOLO.

### Training & Validation
- **`train_pipeline.py`**: A comprehensive wrapper to fine-tune YOLOv8 models. Handles hyperparameters, augmentation configs, and saves the `best.pt` model.
- **`download_advanced_datasets.py`**: Script to fetch specialized datasets (e.g., VisDrone, Argoverse) that contain tiny, distant, or heavily occluded humans.
- **`validate_ov5647.py`**: Runs your custom models against validation video clips to test their real-world performance without needing a live camera.

---

## 3. How to Change Common Settings

### Changing the ML Model Confidence
If the system is rejecting genuine human detections because they are too far away or blurred, you can lower the confidence threshold. Conversely, if it creates false positives, you can raise it.
1. Open `src/hashtag_v2_backend.py`.
2. Locate the `DetectionEngine` initialization inside the `HashtagSystem` class (around line 735).
3. Change the `person_conf` parameter (e.g., `0.20` for smaller models or distant objects, `0.35` for large models/clean feeds).

```python
self.engine = DetectionEngine(
    person_model_path="yolov8s.pt",
    pose_model_path="yolov8s-pose.pt",
    person_conf=0.20, # <--- Lower to detect distant humans, Raise to avoid false positives
    device=None
)
```

### Changing Minimum Frames for a Threat
If an alarm triggers too easily on short blips, require the person to be visible longer.
1. Open `src/hashtag_v2_backend.py`.
2. Change `MIN_FRAMES_FOR_THREAT = 2` (around line 78) to `3` or `4`.
3. Open `src/threat_classifier.py`.
4. Update `self.min_confirm_frames = 2` (around line 580) to match the number above.

### Changing Framerates
1. Open `src/hashtag_v2_backend.py`.
2. Change `TARGET_FPS = 2.0` to the desired rate. Note: Higher framerates drastically increase the time it takes to process a 30-second batch analysis.

---

## 4. Advanced Training: Making Detection Bulletproof

If you find that the current `yolov8s.pt` model fails to detect heavily camouflaged border crossers, or if you intend to switch to Thermal/IR sensors, you will need to train a new model.

### Strategy 1: VisDrone / Argoverse (For Tiny/Distant Humans)
By default, standard YOLO is trained on COCO, which contains large, clear subjects. To detect humans hundreds of meters away:
1. Run `python src/download_advanced_datasets.py` to fetch datasets specifically built for tiny humans.
2. Degrade the datasets using `python src/dataset_manager.py` to match your OV5647 cameras.
3. Fine-tune your model:
   ```bash
   python src/train_pipeline.py --data path/to/visdrone.yaml --epochs 50 --batch 16 --model yolov8s.pt
   ```
4. Move the resulting `runs/hashtag_v2/person_detect/weights/best.pt` to `src/models/` and update `hashtag_v2_backend.py` to use it.

### Strategy 2: RGBT / Thermal / Infrared
If you plan to use IR cameras at night, the visual color model will fail. You must train an RGBT (Red-Green-Blue-Thermal) dataset.
1. Locate the IR datasets in `src/datasets/rgbt-ped-detection` or `HashtagV1_Resources/Misc/Datasets/IR/LLVIP`.
2. Format the annotations into YOLO TXT format.
3. Train the model from scratch (do not use a pre-trained color base, use an empty architecture or freeze early layers):
   ```bash
   python src/train_pipeline.py --data src/datasets/llvip.yaml --epochs 100 --model yolov8n.yaml
   ```

### Strategy 3: Real Custom OV5647 Dataset
The absolute best way to improve reliability is to take the actual MP4 clips saved in `src/Clips`, extract the frames where the system failed, manually draw bounding boxes using a tool like LabelStudio or Roboflow, and train a custom model on those exact frames.
