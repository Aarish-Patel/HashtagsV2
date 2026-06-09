# HashtagV2 — Future Production Roadmap

This document outlines strategic recommendations for scaling the HashtagV2 system from a robust prototype to an enterprise/military-grade distributed platform.

## 1. Advanced Computer Vision & AI

*   **Perspective-Aware Size Thresholding (Ghost Box Fix):** 
    Instead of globally ignoring small bounding boxes (which breaks long-range detection), implement a depth gradient. Objects at the bottom of the camera frame (close to the sensor) must be large, while objects at the top of the frame (near the horizon) are allowed to be small. This filters out 99% of "ghost boxes" like moving leaves in the foreground without losing far-away targets.
*   **TensorRT / ONNX Optimization:**
    Currently, the system runs PyTorch `best.pt` directly. Compiling this model to **NVIDIA TensorRT** or **ONNX** can speed up inference by 2x to 4x, drastically reducing the GPU VRAM overhead and allowing the same hardware to handle twice as many camera nodes.
*   **Multi-Node Re-Identification (Re-ID):**
    If an intruder walks out of the frame of `HASH-1` and into `HASH-2`, the system currently treats them as two separate incidents. A lightweight Re-ID embedding model can track the same entity globally across the entire perimeter.
*   **Thermal & IR Compatibility:**
    Train a supplementary YOLO model on thermal imagery (FLIR cameras) so the system can switch to thermal models automatically at night if MOG2 fails to pick up enough contrast.

## 2. Infrastructure & Deployment

*   **Docker Containerization:**
    Instead of using `launch_hashtag.bat` and requiring manual Python environment setups, package the entire backend into a `docker-compose` stack. This ensures that the system runs identically on any hardware (Linux servers, Windows, Edge devices) and guarantees that dependencies never break.
*   **Edge Computing (NVIDIA Jetson):**
    Instead of streaming all video to a central server for analysis, deploy the YOLO model directly onto the camera nodes using NVIDIA Jetson Orin Nano modules. The cameras only send data to the central server *when a threat is detected*, saving massive amounts of network bandwidth.
*   **Systemd / Watchdog Auto-Recovery:**
    Implement OS-level watchdogs. If the Python process crashes due to a power surge or a memory leak, the OS should automatically reboot the specific service within 5 seconds without human intervention.

## 3. Data Management & Security

*   **Secure Cloud Backup / S3 Sync:**
    Currently, forensic clips are saved to the local `Clips/` directory. If the physical server is compromised or destroyed, the evidence is lost. Implement an asynchronous backup queue that immediately encrypts and pushes confirmed threat clips to an off-site AWS S3 bucket.
*   **Role-Based Access Control (RBAC):**
    The `/admin` dashboard is currently accessible to anyone on the network. Implement JWT (JSON Web Token) authentication with two roles: `OPERATOR` (can view feeds and acknowledge alerts) and `COMMANDER` (can tune YOLO confidence, clear backgrounds, and delete forensic clips).
*   **Encrypted Streams:**
    The MJPEG feeds are currently unencrypted HTTP. In a production military environment, this must be upgraded to WebRTC with DTLS/SRTP encryption to prevent adversaries from intercepting the live feeds.

## 4. UI/UX & Operations

*   **SMS & Webhook Integration:**
    If the operator steps away from the screen, the system should push high-priority threats to mobile devices via Twilio (SMS), Telegram bots, or secure military communication channels.
*   **Intrusion Heatmaps:**
    Aggregate incident data over 30-day periods to generate a visual heatmap over the Tactical Map. This allows commanders to see which sectors of the perimeter are probed most frequently and adjust physical patrols accordingly.
*   **Audio Deterrent Integration:**
    Add an API endpoint that can trigger physical IP-speakers on the fence line to play a recorded warning (e.g., "RESTRICTED AREA. YOU ARE BEING RECORDED.") when a `HIGH` threat is confirmed.
