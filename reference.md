# HashtagV2 Codebase Reference

## Intended Purpose & System Expectations
**Context from User Prompts:**
The overarching goal of this codebase is to provide a highly robust, zero-false-positive, and power-efficient military-grade surveillance system for border or jungle environments. 
Key design decisions enforced by user prompts:
1. **Radar Wake-up Paradigm:** The system operates in "STANDBY" mode. Edge camera nodes (ESP32) remain in deep sleep to conserve power. They only wake up and transmit a 30-second buffer when triggered by a radar (simulated or real). The GPU at the base station sits idle until this buffer is received, processes it in batch mode, and then issues a final threat verdict.
2. **Pure YOLO Optimization:** Originally, the system used a 5-stage pipeline including YOLO pose estimation (skeleton tracking) to verify humans. The user noted this was causing issues and asked to remove pose tracking entirely. The system now uses a **Pure YOLOv8** pipeline. To filter out "mini false positives" (e.g., patterns on a shirt resembling a person), the baseline YOLO confidence threshold was raised to `0.35`. Size-limit checks were removed because people could be far away.
3. **Canny Edge Permanent Background Subtraction:** The user noted that stationary humans would eventually fade into the standard MOG2 background subtractor mask. To solve this, the system incorporates an "Admin-captured" permanent background. Once captured (when the scene is empty), the system uses Canny edge difference (`absdiff` between the live frame edges and the permanent background edges) to generate an incredibly stable motion mask. This ensures a stationary person remains detected indefinitely.
4. **Admin Dashboard / Threat Simulation:** The user requested a separate admin site (not on the main tactical GUI) to:
   - Monitor live raw MJPEG feeds of any dynamically added node.
   - Simulate a threat (inject a fake detection) on any active node to test the downstream alarm/recording pipeline.
   - Run the permanent background capture when the scene has no humans.

## Architecture Overview

### 1. The Backend API (`src/api_server.py`)
- **Framework:** Flask (port 5000)
- **Role:** Handles communication between the frontend GUI and the AI engine.
- **Key Endpoints:**
  - `/video_feed/<node_id>`: Streams the live raw MJPEG feed of a node (standby mode, minimal HUD).
  - `/replay_feed/<job_id>/<node_id>`: Streams the fully annotated MJPEG feed of a 30-second threat clip.
  - `/api/analyze`: Triggered (e.g., by spacebar) to start a batch analysis job on the current 30-second buffer.
  - `/api/admin/simulate_threat/<node_id>`: Injects a fake detection to test the pipeline.
  - `/api/admin/set_background/<node_id>`: Captures the permanent background for the edge-based motion detector.

### 2. The Core Engine (`src/hashtag_v2_backend.py`)
- **`CameraNode`**: Represents a single camera stream. It maintains a live background thread pulling frames. By default, it runs lightweight detection (YOLO) and motion masking (Canny edge diff or MOG2). It maintains a 30s rolling buffer of raw frames.
- **`BatchAnalyzer`**: When the Radar triggers (or an auto-trigger occurs when a camera disconnects after its 30s transmission), this class takes the temporary `.mp4` file and runs heavy ML analysis over the frames at 2.5 FPS. It deduplicates detections, verifies threats, and saves an evidence clip with bounding boxes if a threat is confirmed.
- **`HashtagSystem`**: Orchestrates nodes and batch jobs.

### 3. The Detection Pipeline (`src/detection_engine.py`)
- **`DetectionEngine`**: The ML powerhouse.
  - Loads a custom-trained YOLOv8 model (`best.pt` trained for occlusion/camouflage).
  - **Stage 1**: Full-frame YOLO person detection with a high confidence threshold (`0.35`).
  - **Stage 2**: YOLO COCO weapons detection (classes like knife/scissors). Filters out weapons that don't overlap with a verified person.
  - **Stage 3**: Hierarchical NMS to merge overlapping bounding boxes and absorb smaller boxes contained within larger ones, guaranteeing one clean bounding box per entity.
  
### 4. The Frontend (`frontend/src/`)
- **Admin Dashboard (`AdminDashboard.jsx`)**: A hidden route (`/admin`) for operators to calibrate cameras, configure per-node tuning (YOLO confidence, Canny thresholds), view system telemetry (CPU/RAM/GPU), and simulate threats for testing. Tuning is persisted to `src/node_configs.json`.

## Fast AI Onboarding Tips
1. **Adding a Feature?** If it involves detection logic, look at `detection_engine.py`. If it involves stream handling, buffering, or saving clips, look at `hashtag_v2_backend.py`. For API/Frontend bridges, modify `api_server.py`.
2. **False Positives:** If the system is detecting ghosts, DO NOT add complex filtering heuristics. Simply tune the `person_conf` threshold in `DetectionEngine` or adjust the `TemporalWindowAnalyzer` linearity logic.
3. **Missing Detections:** If the system misses far-away people, ensure `person_conf` isn't too high. Do NOT implement arbitrary size limits (e.g. `if w*h < 500: skip`), as the user explicitly forbids size limits due to far-away targets.
4. **Testing:** Always use the `/admin` dashboard to inject a simulated threat. This tests the entire pipeline (API -> Backend Job -> Video Encoding -> Frontend Alarm) instantly without needing a physical person in the camera view.

## Pending Tasks & Directives for AI Assistants

*Note: The following tasks have been **IMPLEMENTED AND COMPLETED** as of the production v4 update. Kept for historical context.*

1. ✅ **Admin Menu Enhancements:** Added system telemetry, per-node tuning sliders, false positive reporting, background reset controls, and clip retention logic to the dashboard.
2. ✅ **Per-Hashtag (Node) Tuning for False Positives:** Implemented `NodeConfig` dataclass and persisted to `src/node_configs.json`. The engine now accepts `person_conf_override` at runtime.
3. ✅ **Remove "Number of Threats" Count:** All numeric entity counts have been removed from the frontend (Header, Footer, App, EntityTracker).
4. ✅ **Implement Approaching Object = Threat Logic:** Verified humans are always threats (MEDIUM+). Motion blobs that consistently approach are escalated to HIGH threat and trigger a full batch analysis job to identify concealed intruders.

## Open-Ended Questions for AI Analysis
*AI Assistant: Please review the codebase with the following questions in mind to see if anything can be improved, and propose these improvements to the user:*

1. **Scalability:** The batch analyzer processes 30s clips sequentially. Can we optimize GPU memory management or threading if 10 cameras wake up simultaneously?
2. **Motion Masking:** Is `absdiff` with `Canny` edges sufficient for all lighting conditions (day/night)? Should we implement an auto-recalibration of the permanent background if ambient light changes drastically?
3. **Data Management:** Over time, the `Clips/` directory and `forensic_journal.json` will grow. Should there be an automated retention/cleanup policy implemented in the backend?
4. **Admin UX:** What additional telemetry (CPU/GPU usage, memory, stream latency) could be added to the Admin Dashboard to give the operator better debugging visibility?
