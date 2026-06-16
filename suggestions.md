# HashtagV2 — Future Production Roadmap

This document outlines strategic recommendations for scaling the HashtagV2 system from a robust prototype to an enterprise/military-grade distributed platform.

## 1. Advanced Computer Vision & AI

*   **Perspective-Aware Size Thresholding (Ghost Box Fix):** 
    Instead of globally ignoring small bounding boxes (which breaks long-range detection), implement a depth gradient. Objects at the bottom of the camera frame (close to the sensor) must be large, while objects at the top of the frame (near the horizon) are allowed to be small. This filters out 99% of "ghost boxes" like moving leaves in the foreground without losing far-away targets.
*   **TensorRT / ONNX Optimization:**
    Currently, the system runs PyTorch `best.pt` directly. Compiling this model to **NVIDIA TensorRT** or **ONNX** can speed up inference by 2x to 4x, drastically reducing the GPU VRAM overhead and allowing the same hardware to handle twice as many camera nodes.
*   **Multi-Node Re-Identification (Re-ID):**
    If an intruder walks out of the frame of `HASH-1` and into `HASH-2`, the system currently treats them as two separate incidents. A lightweight Re-ID embedding model can track the same entity globally across the entire perimeter.

## 2. Infrastructure & Deployment

*   **Systemd / Watchdog Auto-Recovery:**
    Implement OS-level watchdogs. If the Python process crashes due to a power surge or a memory leak, the OS should automatically reboot the specific service within 5 seconds without human intervention.

## 3. Data Management & Security
*   **Role-Based Access Control (RBAC):**
    The `/admin` dashboard is currently accessible to anyone on the network. Implement JWT (JSON Web Token) authentication with two roles: `OPERATOR` (can view feeds and acknowledge alerts) and `COMMANDER` (can tune YOLO confidence, clear backgrounds, and delete forensic clips).
## 4. UI/UX & Operations

*   **Intrusion Heatmaps:**
    Aggregate incident data over 30-day periods to generate a visual heatmap over the Tactical Map. This allows commanders to see which sectors of the perimeter are probed most frequently and adjust physical patrols accordingly.
